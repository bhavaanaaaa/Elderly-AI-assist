const path = require('path')

/**
 * Explicitly set output/tracing and Turbopack root to the frontend folder
 * to avoid Next.js inferring the workspace root when multiple lockfiles exist.
 */
module.exports = {
  outputFileTracingRoot: path.join(__dirname),
  turbopack: { root: path.join(__dirname) },
}
