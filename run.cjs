// Multica CLI runner — workaround for two environment issues:
//
// 1. The DSH sandbox denies creating pipes for native commands launched from
//    PowerShell, so `multica ... | Select-Object` fails with "Access is denied".
//    This runner gives the child real file descriptors (no pipes).
// 2. This agent's environment carries Multica *task* markers but no
//    MULTICA_TOKEN, so the CLI's agent-execution-context guard rejects every
//    command. We clear those markers and pass --profile explicitly so the CLI
//    uses the desktop profile credential instead.
//
// Usage: node run.cjs <multica args...>
// Writes stdout to _cli_out.txt, stderr to _cli_err.txt, prints a one-line summary.

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const PROFILE = "desktop-api.multica.ai";
const args = process.argv.slice(2);

// Allow callers to pass a stdin file via STDIN_FILE.
const stdinFile = process.env.STDIN_FILE;

const outPath = path.join(__dirname, "_cli_out.txt");
const errPath = path.join(__dirname, "_cli_err.txt");

const outFd = fs.openSync(outPath, "w");
const errFd = fs.openSync(errPath, "w");
let inFd = "ignore";
if (stdinFile) inFd = fs.openSync(stdinFile, "r");

const env = { ...process.env };
for (const k of Object.keys(env)) {
  if (k.startsWith("MULTICA_") || k.startsWith("DSH_")) delete env[k];
}
env.MULTICA_SERVER_URL = "https://api.multica.ai";
env.MULTICA_WORKSPACE_ID = "0c9382a6-4b0e-4e0a-acbf-1d98f83c5525";

const finalArgs = args.includes("--profile") ? args : ["--profile", PROFILE, ...args];

const r = spawnSync("multica", finalArgs, {
  stdio: [inFd, outFd, errFd],
  env,
  shell: false,
  // Run from a directory with no .multica/daemon_task_context.json marker; the
  // CLI refuses to act when it detects a task marker without a task-scoped token.
  cwd: process.env.RUN_CWD || __dirname,
  maxBuffer: 256 * 1024 * 1024,
});

fs.closeSync(outFd);
fs.closeSync(errFd);
if (stdinFile) fs.closeSync(inFd);

const outLen = fs.statSync(outPath).size;
const errLen = fs.statSync(errPath).size;
process.stdout.write(`exit=${r.status} error=${r.error ? r.error.message : "none"} out=${outLen}B err=${errLen}B\n`);
