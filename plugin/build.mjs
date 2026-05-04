// esbuild entry. Builds the SDK for npm consumers AND a single-file IIFE widget
// you can drop into any web page with <script src="widget.iife.js"></script>.
import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const common = {
  bundle: true,
  sourcemap: true,
  target: ["es2020"],
  logLevel: "info",
};

await Promise.all([
  esbuild.build({
    ...common,
    entryPoints: ["src/sdk.ts"],
    outfile: "dist/sdk.js",
    format: "cjs",
    platform: "neutral",
  }),
  esbuild.build({
    ...common,
    entryPoints: ["src/sdk.ts"],
    outfile: "dist/sdk.mjs",
    format: "esm",
    platform: "neutral",
  }),
  esbuild.build({
    ...common,
    entryPoints: ["src/widget.ts"],
    outfile: "dist/widget.iife.js",
    format: "iife",
    globalName: "TradeCopilotWidget",
    platform: "browser",
    minify: true,
  }),
]);

if (watch) {
  console.log("watch mode not implemented — run `npm run build` after edits");
}
