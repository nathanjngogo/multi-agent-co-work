// Generic command runner with real file descriptors (no pipes).
// Usage: node exec.cjs <cmd> [args...]
//   EXEC_CWD      working directory (default: this directory)
//   EXEC_TIMEOUT  ms (default 600000)
// Writes _exec_out.txt / _exec_err.txt next to this file.
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const [cmd, ...args] = process.argv.slice(2);
const outPath = path.join(__dirname, "_exec_out.txt");
const errPath = path.join(__dirname, "_exec_err.txt");
const o = fs.openSync(outPath, "w");
const e = fs.openSync(errPath, "w");

const r = spawnSync(cmd, args, {
  stdio: ["ignore", o, e],
  shell: false,
  cwd: process.env.EXEC_CWD || __dirname,
  timeout: Number(process.env.EXEC_TIMEOUT || 900000),
  maxBuffer: 256 * 1024 * 1024,
});
fs.closeSync(o);
fs.closeSync(e);
console.log(
  `exit=${r.status} error=${r.error ? r.error.message : "none"} out=${fs.statSync(outPath).size}B err=${fs.statSync(errPath).size}B`
);
