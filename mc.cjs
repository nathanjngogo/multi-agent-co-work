// Wrapper: run multica via run.cjs, then echo stdout/stderr to the console.
// Usage: node mc.cjs <multica args...>
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const here = __dirname;
const args = process.argv.slice(2);

const r = spawnSync(process.execPath, [path.join(here, "run.cjs"), ...args], {
  stdio: ["ignore", "inherit", "inherit"],
  env: { ...process.env, RUN_CWD: "C:\\Users\\Administrator" },
  shell: false,
  maxBuffer: 256 * 1024 * 1024,
});

const out = fs.readFileSync(path.join(here, "_cli_out.txt"));
const err = fs.readFileSync(path.join(here, "_cli_err.txt"));
process.stdout.write(out);
if (r.status !== 0) {
  process.stdout.write("\n--- STDERR ---\n");
  process.stdout.write(err);
}
process.exitCode = r.status === null ? 1 : r.status;
