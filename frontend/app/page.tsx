'use client'
import { useEffect, useRef, useState } from 'react'

// ─── CONFIG ────────────────────────────────────────────────────────────────
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const WS  = process.env.NEXT_PUBLIC_WS_URL  || 'ws://localhost:8000/ws/stream'

// ─── TYPES ─────────────────────────────────────────────────────────────────
interface Stats {
  total_detections: number; danger_events: number; fall_events: number
  wet_floor_events: number; ppe_violations: number; crowd_alerts: number
  persons_detected: number; alerts_sent: number;   unique_persons: number
  session_start: string
}
interface Alert { type: string; msg: string; time: string }
interface Incident { timestamp: string; type: string; description: string; severity: string }
interface Detection { timestamp: string; object: string; direction: string; distance: string; status: string; person_count: number; zone: string }

const EMPTY_STATS: Stats = {
  total_detections:0, danger_events:0, fall_events:0, wet_floor_events:0,
  ppe_violations:0, crowd_alerts:0, persons_detected:0, alerts_sent:0,
  unique_persons:0, session_start:''
}

// ─── MINI CHART (pure canvas, no deps) ────────────────────────────────────
function SparkLine({ data, color, height = 40 }: { data: number[]; color: string; height?: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const c = ref.current; if (!c || data.length < 2) return
    const ctx = c.getContext('2d')!
    const w = c.width, h = c.height
    ctx.clearRect(0, 0, w, h)
    const max = Math.max(...data, 1)
    const pts = data.map((v, i) => [i / (data.length - 1) * w, h - (v / max) * h * .85])
    const grad = ctx.createLinearGradient(0, 0, 0, h)
    grad.addColorStop(0, color + '55')
    grad.addColorStop(1, color + '00')
    ctx.beginPath()
    ctx.moveTo(pts[0][0], h)
    pts.forEach(([x, y]) => ctx.lineTo(x, y))
    ctx.lineTo(pts[pts.length - 1][0], h)
    ctx.closePath()
    ctx.fillStyle = grad; ctx.fill()
    ctx.beginPath()
    pts.forEach(([x, y], i) => i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y))
    ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.stroke()
  }, [data, color])
  return <canvas ref={ref} width={200} height={height} style={{ width: '100%', height }} />
}

// ─── HEATMAP (pure canvas) ─────────────────────────────────────────────────
function HeatmapCanvas({ grid }: { grid: number[][] }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const c = ref.current; if (!c) return
    const ctx = c.getContext('2d')!
    const cw = c.width / 10, ch = c.height / 10
    const max = Math.max(...grid.flat(), 1)
    grid.forEach((row, gy) => row.forEach((val, gx) => {
      const t = val / max
      ctx.fillStyle = t < .001
        ? '#060d18'
        : t < .3
        ? `rgba(0,100,180,${t * .8})`
        : t < .7
        ? `rgba(0,210,255,${t})`
        : `rgba(255,${Math.round(220 - t * 180)},0,${t})`
      ctx.fillRect(gx * cw, gy * ch, cw - 1, ch - 1)
    }))
  }, [grid])
  return <canvas ref={ref} width={300} height={200} style={{ width: '100%', height: 200, borderRadius: 8 }} />
}

// ─── MAIN DASHBOARD ────────────────────────────────────────────────────────
export default function Dashboard() {
  // stream
  const [frame,    setFrame]    = useState('')
  const [conn,     setConn]     = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  // detection state
  const [danger,   setDanger]   = useState(false)
  const [fall,     setFall]     = useState(false)
  const [wet,      setWet]      = useState(false)
  const [ppe,      setPpe]      = useState(false)
  const [crowd,    setCrowd]    = useState(false)
  const [persons,  setPersons]  = useState(0)
  const [objects,  setObjects]  = useState<string[]>([])
  const [stats,    setStats]    = useState<Stats>(EMPTY_STATS)
  const [heatmap,  setHeatmap]  = useState<number[][]>(Array(10).fill(null).map(() => Array(10).fill(0)))
  const [alerts,   setAlerts]   = useState<Alert[]>([])

  // history for sparklines
  const [hFall,    setHFall]    = useState<number[]>([0])
  const [hWet,     setHWet]     = useState<number[]>([0])
  const [hPersons, setHPersons] = useState<number[]>([0])
  const [hDanger,  setHDanger]  = useState<number[]>([0])

  // page state
  const [page,     setPage]     = useState<'live'|'analytics'|'incidents'|'reports'|'settings'>('live')
  const [incidents,setIncidents]= useState<Incident[]>([])
  const [detections,setDetections]=useState<Detection[]>([])
  const [aiReport, setAiReport] = useState('')
  const [aiLoading,setAiLoading]= useState(false)
  const [repTab,   setRepTab]   = useState<'inc'|'det'|'ai'>('inc')
  const [statusFilt,setStatusFilt]=useState('')

  // settings state
  const [cfg, setCfg] = useState({
    conf: '0.4', fallSens: '3', crowd: '5', wetArea: '3',
    anthKey: '', twilioSid: '', twilioTok: '', twilioFrom: '+1234567890',
    nursePhone: '+919876543210', emailSend: '', emailPass: '', emailRecv: '',
    sms: false, email: false, wa: false, voice: true,
    wet: true, pose: true, ppe: false, track: false,
  })
  const [savedCfg, setSavedCfg] = useState(false)

  // upload
  const fileRef = useRef<HTMLInputElement>(null)

  // ── WebSocket ───────────────────────────────────────────────────────────
  useEffect(() => {
    let retryTimer: NodeJS.Timeout
    function connect() {
      const ws = new WebSocket(WS)
      wsRef.current = ws
      ws.onopen  = () => setConn(true)
      ws.onclose = () => { setConn(false); retryTimer = setTimeout(connect, 2500) }
      ws.onerror = () => ws.close()
      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data)
          if (d.frame)   setFrame(d.frame)
          setDanger(!!d.danger); setFall(!!d.fall); setWet(!!d.wet)
          setPpe(!!d.ppe); setCrowd(!!d.crowd)
          setPersons(d.person_count ?? 0)
          setObjects(d.objects ?? [])
          if (d.stats) {
            setStats(d.stats)
            setHFall(p  => [...p.slice(-39), d.stats.fall_events      ?? 0])
            setHWet(p   => [...p.slice(-39), d.stats.wet_floor_events  ?? 0])
            setHDanger(p=> [...p.slice(-39), d.stats.danger_events     ?? 0])
            setHPersons(p=> [...p.slice(-39), d.person_count           ?? 0])
          }
          if (d.heatmap)        setHeatmap(d.heatmap)
          if (d.recent_alerts)  setAlerts(d.recent_alerts.slice(0,8))
        } catch {
          // ignore malformed websocket payloads
        }
      }
    }
    connect()
    return () => { clearTimeout(retryTimer); wsRef.current?.close() }
  }, [])

  // ── Poll stats fallback every 6s ────────────────────────────────────────
  useEffect(() => {
    const t = setInterval(() =>
      fetch(`${API}/api/stats`).then(r=>r.json()).then(setStats).catch(()=>{}),
    6000)
    return () => clearInterval(t)
  }, [])

  // ── Load incidents / detections when those pages open ───────────────────
  useEffect(() => {
    if (page === 'incidents' || page === 'reports') {
      fetch(`${API}/api/incidents?limit=200`).then(r=>r.json()).then(d => setIncidents(Array.isArray(d)?d:[])).catch(()=>{})
      fetch(`${API}/api/detections?limit=300${statusFilt?`&status=${statusFilt}`:''}`).then(r=>r.json()).then(d => setDetections(Array.isArray(d)?d:[])).catch(()=>{})
    }
  }, [page, statusFilt])

  // ── Helpers ─────────────────────────────────────────────────────────────
  async function uploadVideo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return
    const fd = new FormData(); fd.append('file', file)
    await fetch(`${API}/api/upload`, { method:'POST', body:fd }).catch(()=>{})
  }

  async function genAiReport() {
    setAiLoading(true); setRepTab('ai')
    const r = await fetch(`${API}/api/ai-report`,{method:'POST'}).catch(()=>null)
    const d = r ? await r.json().catch(()=>({})) : {}
    setAiReport(d.report || d.detail || 'Error — check Anthropic API key in Settings')
    setAiLoading(false)
  }

  async function saveSettings() {
    const updates = [
      {key:'conf_threshold',   value:parseFloat(cfg.conf)},
      {key:'fall_sensitivity', value:parseInt(cfg.fallSens)},
      {key:'crowd_threshold',  value:parseInt(cfg.crowd)},
      {key:'wet_area_ratio',   value:parseInt(cfg.wetArea)/100},
      {key:'enable_wet',       value:cfg.wet},
      {key:'enable_pose',      value:cfg.pose},
      {key:'enable_ppe',       value:cfg.ppe},
      {key:'enable_tracking',  value:cfg.track},
      {key:'enable_sms',       value:cfg.sms},
      {key:'enable_email',     value:cfg.email},
      {key:'enable_whatsapp',  value:cfg.wa},
      {key:'voice_enabled',    value:cfg.voice},
      {key:'anthropic_key',    value:cfg.anthKey},
      {key:'twilio_sid',       value:cfg.twilioSid},
      {key:'twilio_token',     value:cfg.twilioTok},
      {key:'twilio_from',      value:cfg.twilioFrom},
      {key:'nurse_phone',      value:cfg.nursePhone},
      {key:'email_sender',     value:cfg.emailSend},
      {key:'email_password',   value:cfg.emailPass},
      {key:'email_receiver',   value:cfg.emailRecv},
    ]
    await Promise.all(updates.map(u =>
      fetch(`${API}/api/config`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(u)}).catch(()=>{})
    ))
    setSavedCfg(true); setTimeout(()=>setSavedCfg(false),2500)
  }

  // ── Status ───────────────────────────────────────────────────────────────
  const status = fall   ? {icon:'🆘',label:'FALL DETECTED',  color:'#ff6b00',bg:'rgba(255,107,0,.12)',  bd:'rgba(255,107,0,.5)'}
               : danger ? {icon:'🚨',label:'DANGER',         color:'#ff2d55',bg:'rgba(255,45,85,.12)',  bd:'rgba(255,45,85,.5)'}
               : ppe    ? {icon:'🦺',label:'PPE VIOLATION',  color:'#ffd600',bg:'rgba(255,214,0,.1)',   bd:'rgba(255,214,0,.4)'}
               : crowd  ? {icon:'👥',label:'CROWD ALERT',    color:'#bf5fff',bg:'rgba(191,95,255,.1)',  bd:'rgba(191,95,255,.4)'}
               : wet    ? {icon:'💧',label:'WET FLOOR',      color:'#00d4ff',bg:'rgba(0,212,255,.1)',   bd:'rgba(0,212,255,.4)'}
               :          {icon:'✅',label:'ALL CLEAR',      color:'#00e676',bg:'rgba(0,230,118,.08)',  bd:'rgba(0,230,118,.3)'}

  const now = new Date().toLocaleTimeString('en-IN',{hour12:false})

  // ── Style helpers ─────────────────────────────────────────────────────────
  const S = {
    page:     { padding:'20px 24px', position:'relative' as const, zIndex:1, minHeight:'calc(100vh - 60px)', overflowY:'auto' as const },
    card:     { background:'#080f1c', border:'1px solid #0e2035', borderRadius:14, padding:'16px 18px' },
    section:  { fontSize:9, letterSpacing:2, textTransform:'uppercase' as const, color:'#2d4a62', marginBottom:10, fontFamily:'monospace' },
    h1:       { fontFamily:'"Syne",sans-serif', fontWeight:800, fontSize:22, color:'#fff', margin:0 },
    sub:      { fontSize:11, color:'#2d4a62', margin:'3px 0 0', letterSpacing:.4 },
    badge:    (c:string) => ({ padding:'2px 9px', borderRadius:20, fontSize:9, fontWeight:700, fontFamily:'monospace', background:c+'18', border:`1px solid ${c}44`, color:c }),
    input:    { width:'100%', padding:'9px 12px', background:'#040a12', border:'1px solid #0e2035', borderRadius:8, color:'#c8daea', fontSize:11, fontFamily:'monospace', outline:'none' },
    btn:      (c:string,text:string='#04080f') => ({ padding:'8px 18px', background:c, border:'none', borderRadius:9, color:text, fontSize:11, fontWeight:700, cursor:'pointer', fontFamily:'"Syne",sans-serif' }),
    ghostBtn: { padding:'7px 14px', background:'transparent', border:'1px solid #0e2035', borderRadius:8, color:'#2d4a62', fontSize:11, cursor:'pointer' },
  }

  const statCard = (label:string, val:number|string, color:string) => (
    <div key={label} style={{ ...S.card, position:'relative', overflow:'hidden' }}>
      <div style={{ position:'absolute',top:0,left:0,right:0,height:2,background:`linear-gradient(90deg,${color},transparent)` }}/>
      <div style={{ fontFamily:'"Syne",sans-serif',fontWeight:800,fontSize:30,color,lineHeight:1,marginBottom:5 }}>{val??0}</div>
      <div style={{ fontSize:9,letterSpacing:2,textTransform:'uppercase',color:'#2d4a62' }}>{label}</div>
    </div>
  )

  // ── NAV ──────────────────────────────────────────────────────────────────
  const NAV: {id:'live'|'analytics'|'incidents'|'reports'|'settings'; icon:string; label:string}[] = [
    {id:'live',      icon:'📡', label:'Live Monitor'},
    {id:'analytics', icon:'📊', label:'Analytics'},
    {id:'incidents', icon:'🚨', label:'Incidents'},
    {id:'reports',   icon:'📋', label:'Reports'},
    {id:'settings',  icon:'⚙️', label:'Settings'},
  ]

  return (
    <div style={{ display:'flex', minHeight:'100vh', background:'#040a12', color:'#c8daea', fontFamily:'"IBM Plex Mono",monospace' }}>

      {/* ═══════════════════════════════════════════════
          SIDEBAR
      ═══════════════════════════════════════════════ */}
      <aside style={{ width:210, flexShrink:0, background:'#060d18', borderRight:'1px solid #0e2035', display:'flex', flexDirection:'column', position:'fixed', top:0, left:0, bottom:0, zIndex:100 }}>

        {/* Logo */}
        <div style={{ padding:'18px 16px', borderBottom:'1px solid #0e2035' }}>
          <div style={{ display:'flex',alignItems:'center',gap:10,marginBottom:5 }}>
            <div style={{ width:34,height:34,borderRadius:10,background:'rgba(0,212,255,.1)',border:'1px solid rgba(0,212,255,.2)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:17 }}>🏥</div>
            <div>
              <div style={{ fontFamily:'"Syne",sans-serif',fontWeight:800,fontSize:14,color:'#fff' }}>SafeGuard AI</div>
              <div style={{ fontSize:8,letterSpacing:2,color:'#2d4a62',textTransform:'uppercase' }}>IIT Madras · v2.0</div>
            </div>
          </div>
        </div>

        {/* WS Status */}
        <div style={{ margin:'10px 12px 0', padding:'7px 11px', borderRadius:8, background:conn?'rgba(0,230,118,.07)':'rgba(45,74,98,.1)', border:`1px solid ${conn?'rgba(0,230,118,.2)':'#0e2035'}`, display:'flex',alignItems:'center',gap:7,fontSize:10,color:conn?'#00e676':'#2d4a62' }}>
          <span style={{ width:6,height:6,borderRadius:'50%',background:conn?'#00e676':'#2d4a62',display:'inline-block',animation:conn?'blink 1.4s infinite':'none' }}/>
          {conn ? 'BACKEND CONNECTED' : 'CONNECTING...'}
        </div>

        {/* Nav */}
        <nav style={{ flex:1,padding:'12px 10px',display:'flex',flexDirection:'column',gap:2 }}>
          {NAV.map(n => (
            <button key={n.id} onClick={() => setPage(n.id)} style={{
              display:'flex',alignItems:'center',gap:10,padding:'9px 12px',borderRadius:9,
              fontSize:11,fontWeight:500,cursor:'pointer',border:'1px solid',textAlign:'left',
              background: page===n.id ? 'rgba(0,212,255,.08)' : 'transparent',
              borderColor: page===n.id ? 'rgba(0,212,255,.2)' : 'transparent',
              color: page===n.id ? '#00d4ff' : '#2d4a62',
              fontFamily:'"Syne",sans-serif',
            }}>
              <span style={{ fontSize:14,width:18,textAlign:'center' }}>{n.icon}</span>
              {n.label}
            </button>
          ))}
        </nav>

        {/* Mini stats */}
        <div style={{ padding:'12px 14px',borderTop:'1px solid #0e2035' }}>
          <div style={S.section}>session</div>
          {[
            ['Falls',      stats.fall_events,      '#ff6b00'],
            ['Wet Floor',  stats.wet_floor_events,  '#00d4ff'],
            ['Danger',     stats.danger_events,     '#ff2d55'],
            ['PPE',        stats.ppe_violations,    '#ffd600'],
          ].map(([l,v,c]) => (
            <div key={l as string} style={{ display:'flex',justifyContent:'space-between',marginBottom:5 }}>
              <span style={{ fontSize:10,color:'#2d4a62' }}>{l}</span>
              <span style={{ fontFamily:'monospace',fontSize:11,fontWeight:700,color:c as string }}>{v as number ?? 0}</span>
            </div>
          ))}
        </div>
      </aside>

      {/* ═══════════════════════════════════════════════
          MAIN AREA
      ═══════════════════════════════════════════════ */}
      <div style={{ flex:1, marginLeft:210, display:'flex',flexDirection:'column' }}>

        {/* TOP BAR */}
        <div style={{ height:56, background:'#060d18', borderBottom:'1px solid #0e2035', display:'flex',alignItems:'center',justifyContent:'space-between', padding:'0 24px', position:'sticky',top:0,zIndex:50 }}>
          <div>
            <span style={{ fontFamily:'"Syne",sans-serif',fontWeight:700,fontSize:16,color:'#fff' }}>
              Hospital Safety System
            </span>
            <span style={{ fontSize:10,color:'#2d4a62',marginLeft:12 }}>Real-time AI monitoring · IIT Madras</span>
          </div>
          <div style={{ display:'flex',alignItems:'center',gap:10 }}>
            {/* Status pill */}
            <div style={{ display:'flex',alignItems:'center',gap:7,padding:'5px 12px',borderRadius:20,background:status.bg,border:`1px solid ${status.bd}`,fontSize:11,fontWeight:700,color:status.color,fontFamily:'"Syne",sans-serif' }}>
              <span style={{ animation:(fall||danger||wet)?'blink .8s infinite':'none', display:'inline-block' }}>{status.icon}</span>
              {status.label}
            </div>
            <div style={{ padding:'5px 12px',background:'#080f1c',border:'1px solid #0e2035',borderRadius:8,fontSize:11,color:'#2d4a62',fontFamily:'monospace' }}>{now}</div>
            <a href={`${API}/api/download/csv`} download style={{ ...S.ghostBtn, textDecoration:'none' }}>⬇ CSV</a>
            <button onClick={genAiReport} style={S.btn('#00d4ff')}>🤖 AI Report</button>
          </div>
        </div>

        {/* ─────────────────────────────────────────────
            PAGE: LIVE MONITOR
        ───────────────────────────────────────────── */}
        {page === 'live' && (
          <div style={S.page}>

            {/* Alert banner */}
            <div style={{ display:'flex',alignItems:'center',gap:10,padding:'10px 16px',marginBottom:16,borderRadius:10,border:`1px solid ${status.bd}`,background:status.bg,fontSize:11,fontFamily:'monospace' }}>
              <span style={{ fontSize:18 }}>{status.icon}</span>
              <span style={{ fontWeight:700,color:status.color }}>{status.label}</span>
              <span style={{ color:'#2d4a62' }}>
                {fall ? '— Person on ground. Medical staff alerted.' : danger ? '— Dangerous object in frame!' : wet ? '— Slip hazard zone marked on camera.' : ppe ? '— Staff missing protective equipment.' : crowd ? '— Zone density threshold exceeded.' : '— No hazards detected in frame.'}
              </span>
              <span style={{ marginLeft:'auto',color:'#2d4a62',fontSize:10 }}>{now}</span>
            </div>

            {/* Stat cards */}
            <div style={{ display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:10,marginBottom:16 }}>
              {statCard('Total',     stats.total_detections,  '#00d4ff')}
              {statCard('Persons',   persons,                  '#00e676')}
              {statCard('Falls',     stats.fall_events,        '#ff6b00')}
              {statCard('Wet Floor', stats.wet_floor_events,   '#00d4ff')}
              {statCard('Danger',    stats.danger_events,      '#ff2d55')}
              {statCard('PPE',       stats.ppe_violations,     '#ffd600')}
            </div>

            {/* Main grid */}
            <div style={{ display:'grid',gridTemplateColumns:'1fr 290px',gap:14 }}>

              {/* Video feed */}
              <div style={{ ...S.card, padding:0, overflow:'hidden' }}>
                {/* header */}
                <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',padding:'11px 16px',borderBottom:'1px solid #0e2035' }}>
                  <span style={{ fontFamily:'"Syne",sans-serif',fontWeight:600,fontSize:13,color:'#fff' }}>📡 Live Detection Feed</span>
                  <div style={{ display:'flex',gap:8,alignItems:'center' }}>
                    <span style={{ fontSize:10,color:'#2d4a62' }}>Camera 1 — Main Corridor</span>
                    <span style={{ display:'flex',alignItems:'center',gap:4,padding:'2px 8px',borderRadius:20,background:'rgba(255,45,85,.1)',border:'1px solid rgba(255,45,85,.3)',fontSize:9,color:'#ff2d55',fontWeight:700 }}>
                      <span style={{ width:5,height:5,borderRadius:'50%',background:'#ff2d55',animation:'blink 1s infinite',display:'inline-block' }}/>REC
                    </span>
                    <span style={{ padding:'2px 8px',borderRadius:20,fontSize:9,fontWeight:700,background:conn?'rgba(0,230,118,.1)':'rgba(45,74,98,.1)',border:`1px solid ${conn?'rgba(0,230,118,.25)':'#0e2035'}`,color:conn?'#00e676':'#2d4a62' }}>
                      {conn?'● LIVE':'○ OFFLINE'}
                    </span>
                  </div>
                </div>

                {/* frame */}
                <div style={{ background:'#02060d',minHeight:360,position:'relative',display:'flex',alignItems:'center',justifyContent:'center',overflow:'hidden' }}>
                  {/* scanlines */}
                  <div style={{ position:'absolute',inset:0,backgroundImage:'repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.03) 2px,rgba(0,0,0,.03) 4px)',pointerEvents:'none',zIndex:2 }}/>
                  {frame
                    ? <>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={`data:image/jpeg;base64,${frame}`} style={{ width:'100%',display:'block' }} alt="Live detection"/>
                      </>
                    : <div style={{ textAlign:'center',color:'#2d4a62',zIndex:1 }}>
                        <div style={{ fontSize:40,marginBottom:12 }}>📷</div>
                        <div style={{ fontSize:13 }}>Waiting for stream...</div>
                        <div style={{ fontSize:9,marginTop:6,color:'#0e2035',fontFamily:'monospace' }}>{WS}</div>
                      </div>
                  }
                  {/* overlays */}
                  {fall && <div style={{ position:'absolute',bottom:12,left:12,right:12,background:'rgba(255,107,0,.92)',borderRadius:8,padding:'8px 12px',fontSize:11,fontFamily:'monospace',color:'#fff',zIndex:3,animation:'blink .7s infinite' }}>🆘 FALL DETECTED — Alerting medical staff</div>}
                  {!fall&&wet && <div style={{ position:'absolute',bottom:12,left:12,right:12,background:'rgba(0,212,255,.15)',border:'1px solid rgba(0,212,255,.5)',borderRadius:8,padding:'8px 12px',fontSize:11,fontFamily:'monospace',color:'#00d4ff',zIndex:3 }}>💧 WET FLOOR — Slip hazard marked on frame</div>}
                  {!fall&&!wet&&danger && <div style={{ position:'absolute',bottom:12,left:12,right:12,background:'rgba(255,45,85,.15)',border:'1px solid rgba(255,45,85,.5)',borderRadius:8,padding:'8px 12px',fontSize:11,fontFamily:'monospace',color:'#ff2d55',zIndex:3,animation:'blink .5s infinite' }}>🚨 DANGEROUS OBJECT DETECTED</div>}
                </div>

                {/* source bar */}
                <div style={{ display:'flex',gap:8,padding:'10px 14px',borderTop:'1px solid #0e2035',background:'#060d18' }}>
                  <button onClick={() => fetch(`${API}/api/source`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:'0'})})} style={S.btn('#00d4ff','#04080f')}>📹 Webcam</button>
                  <label style={{ ...S.ghostBtn, display:'flex',alignItems:'center',cursor:'pointer' }}>
                    📁 Upload Video
                    <input ref={fileRef} type="file" accept=".mp4,.avi,.mov,.mkv" style={{ display:'none' }} onChange={uploadVideo}/>
                  </label>
                  <div style={{ marginLeft:'auto',display:'flex',alignItems:'center',gap:5,fontSize:10,color:'#2d4a62' }}>
                    <span style={{ width:5,height:5,borderRadius:'50%',background:conn?'#00e676':'#2d4a62',display:'inline-block',animation:conn?'blink 1.5s infinite':'none' }}/>
                    {conn?'~30 FPS':'—'}
                  </div>
                </div>
              </div>

              {/* Right column */}
              <div style={{ display:'flex',flexDirection:'column',gap:12 }}>

                {/* Status card */}
                <div style={{ ...S.card, border:`1px solid ${status.bd}`, background:status.bg }}>
                  <div style={{ display:'flex',alignItems:'center',gap:12,marginBottom:12 }}>
                    <span style={{ fontSize:30 }}>{status.icon}</span>
                    <div>
                      <div style={{ fontFamily:'"Syne",sans-serif',fontWeight:800,fontSize:20,color:status.color }}>{status.label}</div>
                      <div style={{ fontSize:10,color:'#2d4a62',marginTop:2 }}>{persons} persons in frame</div>
                    </div>
                  </div>
                  <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:8,paddingTop:12,borderTop:'1px solid #0e2035' }}>
                    {[['Persons',persons,'#00d4ff'],['Unique IDs',stats.unique_persons,'#00e676'],['Alerts',stats.alerts_sent,'#ffd600']].map(([l,v,c])=>(
                      <div key={l as string} style={{ textAlign:'center' }}>
                        <div style={{ fontFamily:'monospace',fontSize:20,fontWeight:700,color:c as string }}>{v as number??0}</div>
                        <div style={{ fontSize:8,letterSpacing:1.5,textTransform:'uppercase',color:'#2d4a62',marginTop:2 }}>{l}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Alert log */}
                <div style={{ ...S.card, flex:1 }}>
                  <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:10 }}>
                    <span style={{ fontFamily:'"Syne",sans-serif',fontWeight:600,fontSize:13,color:'#fff' }}>📢 Alert Log</span>
                    <span style={{ fontSize:9,padding:'2px 7px',background:'#0e2035',borderRadius:10,color:'#2d4a62' }}>{alerts.length}</span>
                  </div>
                  <div style={{ maxHeight:180,overflowY:'auto',display:'flex',flexDirection:'column',gap:4 }}>
                    {alerts.length===0
                      ? <div style={{ fontSize:10,color:'#2d4a62',textAlign:'center',padding:16 }}>No alerts yet</div>
                      : alerts.map((a,i)=>{
                          const c = a.type==='fall'?'#ff6b00':a.type==='danger'?'#ff2d55':a.type==='wet'?'#00d4ff':'#bf5fff'
                          return <div key={i} style={{ padding:'6px 10px',borderRadius:7,fontSize:10,fontFamily:'monospace',display:'flex',gap:6,background:c+'10',border:`1px solid ${c}22`,color:c }}>
                            <span style={{ opacity:.5 }}>[{a.time}]</span><span>{a.msg}</span>
                          </div>
                        })
                    }
                  </div>
                </div>

                {/* Detected objects */}
                <div style={S.card}>
                  <div style={{ fontFamily:'"Syne",sans-serif',fontWeight:600,fontSize:13,color:'#fff',marginBottom:10 }}>🎯 Objects</div>
                  <div style={{ display:'flex',flexWrap:'wrap',gap:5 }}>
                    {objects.length===0
                      ? <span style={{ fontSize:10,color:'#2d4a62' }}>Waiting...</span>
                      : [...new Set(objects)].map(o=>(
                          <span key={o} style={{ ...S.badge(o==='person'?'#ff6b00':['knife','gun','fire','smoke'].includes(o)?'#ff2d55':'#00e676') }}>{o}</span>
                        ))
                    }
                  </div>
                </div>

              </div>
            </div>
          </div>
        )}

        {/* ─────────────────────────────────────────────
            PAGE: ANALYTICS
        ───────────────────────────────────────────── */}
        {page === 'analytics' && (
          <div style={S.page}>
            <div style={{ marginBottom:18 }}>
              <h1 style={S.h1}>Analytics</h1>
              <p style={S.sub}>Live detection trends · sparklines · heatmap</p>
            </div>

            {/* Stat cards */}
            <div style={{ display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:10,marginBottom:18 }}>
              {statCard('Total',     stats.total_detections, '#00d4ff')}
              {statCard('Danger',    stats.danger_events,    '#ff2d55')}
              {statCard('Falls',     stats.fall_events,      '#ff6b00')}
              {statCard('Wet Floor', stats.wet_floor_events, '#00d4ff')}
              {statCard('PPE',       stats.ppe_violations,   '#ffd600')}
              {statCard('Crowd',     stats.crowd_alerts,     '#bf5fff')}
            </div>

            {/* Sparklines */}
            <div style={{ display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:12,marginBottom:14 }}>
              {[
                {label:'Person Count',  data:hPersons, color:'#00e676'},
                {label:'Fall Events',   data:hFall,    color:'#ff6b00'},
                {label:'Wet Floor',     data:hWet,     color:'#00d4ff'},
                {label:'Danger Events', data:hDanger,  color:'#ff2d55'},
              ].map(({label,data,color})=>(
                <div key={label} style={S.card}>
                  <div style={{ display:'flex',justifyContent:'space-between',marginBottom:8 }}>
                    <span style={{ fontFamily:'"Syne",sans-serif',fontWeight:600,fontSize:12,color:'#fff' }}>{label}</span>
                    <span style={{ fontFamily:'monospace',fontSize:16,fontWeight:700,color }}>{data[data.length-1]??0}</span>
                  </div>
                  <SparkLine data={data} color={color}/>
                </div>
              ))}
            </div>

            {/* Heatmap */}
            <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:14 }}>
              <div style={S.card}>
                <div style={{ fontFamily:'"Syne",sans-serif',fontWeight:600,fontSize:13,color:'#fff',marginBottom:10 }}>🗺️ Spatial Activity Heatmap</div>
                <p style={{ fontSize:10,color:'#2d4a62',marginBottom:10 }}>Brighter = more activity. Wet floor events weighted 2×</p>
                <HeatmapCanvas grid={heatmap}/>
                <div style={{ display:'flex',justifyContent:'space-between',marginTop:8,fontSize:9,color:'#2d4a62' }}>
                  <span>← Left</span><span>Center</span><span>Right →</span>
                </div>
                <button onClick={() => fetch(`${API}/api/heatmap`,{method:'DELETE'})} style={{ ...S.ghostBtn, marginTop:10, fontSize:10 }}>↺ Reset Heatmap</button>
              </div>

              <div style={S.card}>
                <div style={{ fontFamily:'"Syne",sans-serif',fontWeight:600,fontSize:13,color:'#fff',marginBottom:14 }}>📊 Event Breakdown</div>
                {[
                  {label:'Fall Events',      val:stats.fall_events,      max:Math.max(stats.total_detections,1), color:'#ff6b00'},
                  {label:'Wet Floor Events', val:stats.wet_floor_events,  max:Math.max(stats.total_detections,1), color:'#00d4ff'},
                  {label:'Danger Events',    val:stats.danger_events,    max:Math.max(stats.total_detections,1), color:'#ff2d55'},
                  {label:'PPE Violations',   val:stats.ppe_violations,   max:Math.max(stats.total_detections,1), color:'#ffd600'},
                  {label:'Crowd Alerts',     val:stats.crowd_alerts,     max:Math.max(stats.total_detections,1), color:'#bf5fff'},
                ].map(({label,val,max,color})=>(
                  <div key={label} style={{ marginBottom:12 }}>
                    <div style={{ display:'flex',justifyContent:'space-between',marginBottom:4 }}>
                      <span style={{ fontSize:11,color:'#c8daea' }}>{label}</span>
                      <span style={{ fontFamily:'monospace',fontSize:11,fontWeight:700,color }}>{val??0}</span>
                    </div>
                    <div style={{ height:4,background:'#0e2035',borderRadius:2,overflow:'hidden' }}>
                      <div style={{ height:'100%',width:`${Math.min((val??0)/max*100*8,100)}%`,background:color,borderRadius:2,transition:'width .6s ease' }}/>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ─────────────────────────────────────────────
            PAGE: INCIDENTS
        ───────────────────────────────────────────── */}
        {page === 'incidents' && (
          <div style={S.page}>
            <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:18 }}>
              <div><h1 style={S.h1}>Incidents</h1><p style={S.sub}>All detected incidents · live from SQLite database</p></div>
              <button onClick={() => fetch(`${API}/api/incidents?limit=200`).then(r=>r.json()).then(d=>setIncidents(Array.isArray(d)?d:[]))} style={S.ghostBtn}>↻ Refresh</button>
            </div>

            <div style={{ display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:10,marginBottom:18 }}>
              {statCard('Total',    incidents.length, '#fff')}
              {statCard('Critical', incidents.filter(i=>i.severity==='CRITICAL').length, '#ff2d55')}
              {statCard('High',     incidents.filter(i=>i.severity==='HIGH').length,     '#ff6b00')}
              {statCard('Medium',   incidents.filter(i=>i.severity==='MEDIUM').length,   '#00d4ff')}
            </div>

            {/* Filters */}
            <div style={{ display:'flex',gap:6,marginBottom:12 }}>
              {['ALL','CRITICAL','HIGH','MEDIUM'].map(s=>(
                <button key={s} onClick={()=>{}} style={{ padding:'5px 14px',borderRadius:8,fontSize:10,cursor:'pointer',border:'1px solid #0e2035',background:'transparent',color:'#2d4a62' }}>{s}</button>
              ))}
              <div style={{ marginLeft:'auto',display:'flex',alignItems:'center',gap:4,fontSize:10,color:'#2d4a62' }}>
                <span style={{ width:6,height:6,borderRadius:'50%',background:'#00e676',animation:'blink 1.4s infinite',display:'inline-block' }}/>
                Auto-refresh every 5s
              </div>
            </div>

            <div style={{ ...S.card, padding:0, overflow:'hidden' }}>
              <table style={{ width:'100%',borderCollapse:'collapse' }}>
                <thead>
                  <tr style={{ borderBottom:'1px solid #0e2035' }}>
                    {['Timestamp','Type','Description','Severity'].map(h=>(
                      <th key={h} style={{ textAlign:'left',padding:'10px 14px',fontSize:9,letterSpacing:2,textTransform:'uppercase',color:'#2d4a62',fontWeight:500 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {incidents.length===0
                    ? <tr><td colSpan={4} style={{ textAlign:'center',padding:36,color:'#2d4a62',fontSize:11 }}>No incidents yet — start detection</td></tr>
                    : incidents.map((inc,i)=>{
                        const sc = inc.severity==='CRITICAL'?'#ff2d55':inc.severity==='HIGH'?'#ff6b00':'#00d4ff'
                        const typeIcon = inc.type?.includes('FALL')?'🆘':inc.type?.includes('WET')?'💧':inc.type?.includes('PPE')?'🦺':inc.type?.includes('DANGER')?'🚨':'📌'
                        return <tr key={i} style={{ borderBottom:'1px solid rgba(14,32,53,.6)',transition:'.15s' }}>
                          <td style={{ padding:'9px 14px',fontSize:10,fontFamily:'monospace',color:'#2d4a62',whiteSpace:'nowrap' }}>{inc.timestamp}</td>
                          <td style={{ padding:'9px 14px',fontSize:11,color:'#c8daea' }}>{typeIcon} {inc.type?.replace(/_/g,' ')}</td>
                          <td style={{ padding:'9px 14px',fontSize:10,fontFamily:'monospace',color:'#2d4a62' }}>{inc.description}</td>
                          <td style={{ padding:'9px 14px' }}><span style={S.badge(sc)}>{inc.severity}</span></td>
                        </tr>
                      })
                  }
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ─────────────────────────────────────────────
            PAGE: REPORTS
        ───────────────────────────────────────────── */}
        {page === 'reports' && (
          <div style={S.page}>
            <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:18 }}>
              <div><h1 style={S.h1}>Reports</h1><p style={S.sub}>Incident log · detection history · Claude AI analysis</p></div>
              <div style={{ display:'flex',gap:8 }}>
                <a href={`${API}/api/download/csv`} download style={{ ...S.ghostBtn,textDecoration:'none',display:'flex',alignItems:'center',gap:5 }}>⬇ CSV</a>
                <button onClick={genAiReport} disabled={aiLoading} style={S.btn('#00d4ff','#04080f')}>
                  {aiLoading?'🤖 Generating...':'🤖 Generate AI Report'}
                </button>
                <button onClick={async()=>{await fetch(`${API}/api/stats`,{method:'DELETE'});window.location.reload()}} style={{ ...S.ghostBtn,borderColor:'rgba(255,45,85,.3)',color:'#ff2d55' }}>🗑 Clear</button>
              </div>
            </div>

            {/* Stat row */}
            <div style={{ display:'grid',gridTemplateColumns:'repeat(7,1fr)',gap:8,marginBottom:16 }}>
              {[['Total',stats.total_detections,'#fff'],['Danger',stats.danger_events,'#ff2d55'],['Falls',stats.fall_events,'#ff6b00'],['Wet',stats.wet_floor_events,'#00d4ff'],['PPE',stats.ppe_violations,'#ffd600'],['Crowd',stats.crowd_alerts,'#bf5fff'],['Alerts',stats.alerts_sent,'#00e676']].map(([l,v,c])=>(
                <div key={l as string} style={{ ...S.card,textAlign:'center',padding:'10px 8px' }}>
                  <div style={{ fontFamily:'"Syne",sans-serif',fontWeight:800,fontSize:22,color:c as string,lineHeight:1,marginBottom:3 }}>{v as number??0}</div>
                  <div style={{ fontSize:8,letterSpacing:1.5,textTransform:'uppercase',color:'#2d4a62' }}>{l}</div>
                </div>
              ))}
            </div>

            {/* Tabs */}
            <div style={{ display:'flex',gap:4,marginBottom:14,borderBottom:'1px solid #0e2035',paddingBottom:10 }}>
              {([['inc',`Incidents (${incidents.length})`],['det',`Detection Log (${detections.length})`],['ai','🤖 AI Report']] as Array<['inc'|'det'|'ai', string]>).map(([id,label])=>(
                <button key={id} onClick={()=>setRepTab(id)} style={{ padding:'6px 16px',borderRadius:8,fontSize:11,cursor:'pointer',border:'1px solid',background:repTab===id?'rgba(0,212,255,.1)':'transparent',borderColor:repTab===id?'rgba(0,212,255,.3)':'transparent',color:repTab===id?'#00d4ff':'#2d4a62',fontFamily:'"Syne",sans-serif' }}>{label}</button>
              ))}
            </div>

            {repTab==='inc' && (
              <div style={{ ...S.card,padding:0,overflow:'auto' }}>
                <table style={{ width:'100%',borderCollapse:'collapse' }}>
                  <thead><tr style={{ borderBottom:'1px solid #0e2035' }}>
                    {['Time','Type','Description','Severity'].map(h=><th key={h} style={{ textAlign:'left',padding:'9px 14px',fontSize:9,letterSpacing:2,textTransform:'uppercase',color:'#2d4a62' }}>{h}</th>)}
                  </tr></thead>
                  <tbody>
                    {incidents.length===0?<tr><td colSpan={4} style={{ textAlign:'center',padding:28,color:'#2d4a62',fontSize:11 }}>No incidents</td></tr>
                    :incidents.map((inc,i)=>{
                      const sc=inc.severity==='CRITICAL'?'#ff2d55':inc.severity==='HIGH'?'#ff6b00':'#00d4ff'
                      return <tr key={i} style={{ borderBottom:'1px solid rgba(14,32,53,.5)' }}>
                        <td style={{ padding:'8px 14px',fontSize:10,fontFamily:'monospace',color:'#2d4a62' }}>{inc.timestamp}</td>
                        <td style={{ padding:'8px 14px',fontSize:11,color:'#c8daea' }}>{inc.type?.replace(/_/g,' ')}</td>
                        <td style={{ padding:'8px 14px',fontSize:10,fontFamily:'monospace',color:'#2d4a62' }}>{inc.description}</td>
                        <td style={{ padding:'8px 14px' }}><span style={S.badge(sc)}>{inc.severity}</span></td>
                      </tr>
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {repTab==='det' && (
              <div>
                <div style={{ display:'flex',gap:5,marginBottom:10,flexWrap:'wrap' }}>
                  {['','DANGER','FALL','WET','PPE','CROWD','SAFE'].map(s=>(
                    <button key={s} onClick={()=>setStatusFilt(s)} style={{ padding:'4px 12px',borderRadius:7,fontSize:10,cursor:'pointer',border:'1px solid',background:statusFilt===s?'rgba(0,212,255,.1)':'transparent',borderColor:statusFilt===s?'rgba(0,212,255,.3)':'#0e2035',color:statusFilt===s?'#00d4ff':'#2d4a62' }}>{s||'All'}</button>
                  ))}
                </div>
                <div style={{ ...S.card,padding:0,overflow:'auto',maxHeight:'60vh' }}>
                  <table style={{ width:'100%',borderCollapse:'collapse' }}>
                    <thead><tr style={{ borderBottom:'1px solid #0e2035',position:'sticky',top:0,background:'#080f1c' }}>
                      {['Time','Object','Direction','Distance','Status','Persons'].map(h=><th key={h} style={{ textAlign:'left',padding:'9px 12px',fontSize:9,letterSpacing:2,textTransform:'uppercase',color:'#2d4a62' }}>{h}</th>)}
                    </tr></thead>
                    <tbody>
                      {detections.map((d,i)=>{
                        const sc = d.status==='DANGER'?'#ff2d55':d.status==='FALL'?'#ff6b00':d.status==='WET'?'#00d4ff':d.status==='PPE'?'#ffd600':'#00e676'
                        return <tr key={i} style={{ borderBottom:'1px solid rgba(14,32,53,.4)' }}>
                          <td style={{ padding:'8px 12px',fontSize:10,fontFamily:'monospace',color:'#2d4a62',whiteSpace:'nowrap' }}>{d.timestamp?.slice(11,19)}</td>
                          <td style={{ padding:'8px 12px',fontSize:11,color:'#c8daea' }}>{d.object}</td>
                          <td style={{ padding:'8px 12px',fontSize:10,color:'#2d4a62' }}>{d.direction}</td>
                          <td style={{ padding:'8px 12px',fontSize:10,color:'#2d4a62' }}>{d.distance}</td>
                          <td style={{ padding:'8px 12px' }}><span style={S.badge(sc)}>{d.status}</span></td>
                          <td style={{ padding:'8px 12px',fontSize:10,fontFamily:'monospace',color:'#00d4ff' }}>{d.person_count}</td>
                        </tr>
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {repTab==='ai' && (
              <div style={S.card}>
                {aiLoading ? (
                  <div style={{ textAlign:'center',padding:40,color:'#2d4a62' }}>
                    <div style={{ fontSize:36,marginBottom:12,animation:'spin 2s linear infinite',display:'inline-block' }}>🤖</div>
                    <div style={{ fontSize:12 }}>Claude is analyzing your safety data...</div>
                  </div>
                ) : !aiReport ? (
                  <div style={{ textAlign:'center',padding:40 }}>
                    <div style={{ fontSize:40,marginBottom:10 }}>🤖</div>
                    <p style={{ color:'#2d4a62',fontSize:13 }}>Click <b style={{color:'#fff'}}>Generate AI Report</b> above</p>
                    <p style={{ color:'#0e2035',fontSize:10,marginTop:6,fontFamily:'monospace' }}>Requires Anthropic API key in Settings</p>
                  </div>
                ) : (
                  <div>
                    <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:14 }}>
                      <span style={{ fontFamily:'"Syne",sans-serif',fontWeight:600,fontSize:13,color:'#fff' }}>Claude AI Safety Report</span>
                      <button onClick={()=>{const b=new Blob([aiReport],{type:'text/plain'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=`report_${Date.now()}.txt`;a.click()}} style={S.ghostBtn}>⬇ Download</button>
                    </div>
                    <pre style={{ background:'#04080f',borderRadius:10,border:'1px solid rgba(0,230,118,.15)',padding:16,fontFamily:'monospace',fontSize:11,color:'#00e676',lineHeight:1.8,whiteSpace:'pre-wrap',maxHeight:'60vh',overflowY:'auto' }}>{aiReport}</pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ─────────────────────────────────────────────
            PAGE: SETTINGS
        ───────────────────────────────────────────── */}
        {page === 'settings' && (
          <div style={S.page}>
            <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:18 }}>
              <div><h1 style={S.h1}>Settings</h1><p style={S.sub}>Alert config · detection thresholds · API keys · feature toggles</p></div>
              <button onClick={saveSettings} style={S.btn(savedCfg?'#00e676':'#00d4ff','#04080f')}>
                {savedCfg?'✅ Saved!':'💾 Save All Settings'}
              </button>
            </div>

            <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:14 }}>
              {/* Left */}
              <div style={{ display:'flex',flexDirection:'column',gap:14 }}>
                <div style={S.card}>
                  <div style={S.section}>Detection Thresholds</div>
                  {( [
                    ['Confidence Threshold (0.2–0.9)', cfg.conf, (v:string)=>setCfg(p=>({...p,conf:v}))],
                    ['Fall Sensitivity (1–5)',          cfg.fallSens, (v:string)=>setCfg(p=>({...p,fallSens:v}))],
                    ['Crowd Alert — Max persons/zone',  cfg.crowd,    (v:string)=>setCfg(p=>({...p,crowd:v}))],
                    ['Min Spill Size (% of frame 1-20)',cfg.wetArea,  (v:string)=>setCfg(p=>({...p,wetArea:v}))],
                  ] as Array<[string,string,(v:string)=>void]>).map(([label,val,fn])=>(
                    <div key={label} style={{ marginBottom:12 }}>
                      <label style={{ display:'block',fontSize:11,color:'#c8daea',marginBottom:5 }}>{label}</label>
                      <input value={val} onChange={e=>fn(e.target.value)} style={S.input}
                        onFocus={e=>e.target.style.borderColor='rgba(0,212,255,.4)'}
                        onBlur={e=>e.target.style.borderColor='#0e2035'}/>
                    </div>
                  ))}
                </div>

                <div style={S.card}>
                  <div style={S.section}>Feature Toggles</div>
                  {( [
                    ['Wet Floor Detection',  '5-method HSV voting',    cfg.wet,   ()=>setCfg(p=>({...p,wet:!p.wet}))],
                    ['Pose Fall Detection',  'MediaPipe skeleton',     cfg.pose,  ()=>setCfg(p=>({...p,pose:!p.pose}))],
                    ['PPE Detection',        'Custom YOLO model req.',  cfg.ppe,   ()=>setCfg(p=>({...p,ppe:!p.ppe}))],
                    ['DeepSORT Tracking',    'Persistent person IDs',  cfg.track, ()=>setCfg(p=>({...p,track:!p.track}))],
                    ['Voice Alerts',         'pyttsx3 TTS engine',     cfg.voice, ()=>setCfg(p=>({...p,voice:!p.voice}))],
                  ] as Array<[string,string,boolean,()=>void]>).map(([label,sub,checked,fn])=>(
                    <div key={label} style={{ display:'flex',justifyContent:'space-between',alignItems:'center',padding:'9px 0',borderBottom:'1px solid #0e2035' }}>
                      <div>
                        <div style={{ fontSize:12,color:'#c8daea' }}>{label}</div>
                        <div style={{ fontSize:10,color:'#2d4a62',marginTop:1 }}>{sub}</div>
                      </div>
                      <div onClick={fn} style={{ width:40,height:21,borderRadius:11,cursor:'pointer',position:'relative',transition:'.2s',background:checked?'#00d4ff':'#0e2035' }}>
                        <div style={{ width:15,height:15,borderRadius:'50%',background:'#fff',position:'absolute',top:3,left:checked?22:3,transition:'.2s' }}/>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right */}
              <div style={{ display:'flex',flexDirection:'column',gap:14 }}>
                <div style={S.card}>
                  <div style={S.section}>Claude AI Reports</div>
                  <div style={{ marginBottom:6 }}>
                    <label style={{ display:'block',fontSize:11,color:'#c8daea',marginBottom:5 }}>Anthropic API Key</label>
                    <input type="password" placeholder="sk-ant-..." value={cfg.anthKey} onChange={e=>setCfg(p=>({...p,anthKey:e.target.value}))} style={S.input}
                      onFocus={e=>e.target.style.borderColor='rgba(0,212,255,.4)'} onBlur={e=>e.target.style.borderColor='#0e2035'}/>
                  </div>
                  <div style={{ fontSize:10,color:'#2d4a62' }}>Get key from console.anthropic.com</div>
                </div>

                <div style={S.card}>
                  <div style={S.section}>Alert Channels</div>

                  {/* SMS Toggle */}
                  <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid #0e2035',marginBottom:cfg.sms?10:0 }}>
                    <div><div style={{ fontSize:12,color:'#c8daea' }}>SMS (Twilio)</div><div style={{ fontSize:10,color:'#2d4a62' }}>Send SMS to nurse</div></div>
                    <div onClick={()=>setCfg(p=>({...p,sms:!p.sms}))} style={{ width:40,height:21,borderRadius:11,cursor:'pointer',position:'relative',transition:'.2s',background:cfg.sms?'#00d4ff':'#0e2035' }}>
                      <div style={{ width:15,height:15,borderRadius:'50%',background:'#fff',position:'absolute',top:3,left:cfg.sms?22:3,transition:'.2s' }}/>
                    </div>
                  </div>
                  {cfg.sms && ['Twilio SID','Twilio Token','From Number','Nurse Phone'].map((l,i)=>(
                    <div key={l} style={{ marginBottom:8 }}>
                      <label style={{ display:'block',fontSize:10,color:'#2d4a62',marginBottom:4 }}>{l}</label>
                      <input type={l.includes('Token')||l.includes('SID')?'password':'text'}
                        value={[cfg.twilioSid,cfg.twilioTok,cfg.twilioFrom,cfg.nursePhone][i]}
                        onChange={e=>setCfg(p=>({...p,...[{twilioSid:e.target.value},{twilioTok:e.target.value},{twilioFrom:e.target.value},{nursePhone:e.target.value}][i]}))}
                        style={{ ...S.input,fontSize:10 }}
                        onFocus={e=>e.target.style.borderColor='rgba(0,212,255,.4)'} onBlur={e=>e.target.style.borderColor='#0e2035'}/>
                    </div>
                  ))}

                  {/* Email Toggle */}
                  <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid #0e2035',borderTop:'1px solid #0e2035',marginTop:8,marginBottom:cfg.email?10:0 }}>
                    <div><div style={{ fontSize:12,color:'#c8daea' }}>Email Alerts</div><div style={{ fontSize:10,color:'#2d4a62' }}>Gmail SMTP</div></div>
                    <div onClick={()=>setCfg(p=>({...p,email:!p.email}))} style={{ width:40,height:21,borderRadius:11,cursor:'pointer',position:'relative',transition:'.2s',background:cfg.email?'#00d4ff':'#0e2035' }}>
                      <div style={{ width:15,height:15,borderRadius:'50%',background:'#fff',position:'absolute',top:3,left:cfg.email?22:3,transition:'.2s' }}/>
                    </div>
                  </div>
                  {cfg.email && ['Sender Email','Gmail Password','Receiver Email'].map((l,i)=>(
                    <div key={l} style={{ marginBottom:8 }}>
                      <label style={{ display:'block',fontSize:10,color:'#2d4a62',marginBottom:4 }}>{l}</label>
                      <input type={l.includes('Password')?'password':'email'}
                        value={[cfg.emailSend,cfg.emailPass,cfg.emailRecv][i]}
                        onChange={e=>setCfg(p=>({...p,...[{emailSend:e.target.value},{emailPass:e.target.value},{emailRecv:e.target.value}][i]}))}
                        style={{ ...S.input,fontSize:10 }}
                        onFocus={e=>e.target.style.borderColor='rgba(0,212,255,.4)'} onBlur={e=>e.target.style.borderColor='#0e2035'}/>
                    </div>
                  ))}
                </div>

                <div style={S.card}>
                  <div style={S.section}>Backend Status</div>
                  <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:8 }}>
                    {[['API URL','localhost:8000'],['WS Stream','/ws/stream'],['Swagger','/docs'],['Database','hospital_safety.db']].map(([l,v])=>(
                      <div key={l} style={{ background:'#04080f',border:'1px solid #0e2035',borderRadius:8,padding:'8px 10px' }}>
                        <div style={{ fontSize:8,letterSpacing:1.5,textTransform:'uppercase',color:'#2d4a62',marginBottom:3 }}>{l}</div>
                        <div style={{ fontFamily:'monospace',fontSize:10,color:'#00d4ff' }}>{v}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

      </div>

      {/* Global styles */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #040a12 !important; }
        body::before {
          content: '';
          position: fixed; inset: 0; pointer-events: none; z-index: 0;
          background-image: linear-gradient(#0a1a2a 1px, transparent 1px), linear-gradient(90deg, #0a1a2a 1px, transparent 1px);
          background-size: 44px 44px;
          opacity: .4;
        }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.2} }
        @keyframes spin  { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: #040a12; }
        ::-webkit-scrollbar-thumb { background: #0e2035; border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover { background: #1a3050; }
      `}</style>
    </div>
  )
}