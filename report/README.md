# v1 report and presentation

- [STAGE3_REPORT.pdf](STAGE3_REPORT.pdf): written v1 report.
- [stage3_report.html](stage3_report.html): report source. Open it in a browser to read or print to PDF; exact pagination depends on the browser and fonts.
- [LLM_Markets_Presentation.pptx](LLM_Markets_Presentation.pptx): v1 presentation.
- [deck/build_deck.js](deck/build_deck.js): presentation source, using the committed PNG figures in `analysis/figures/`.

For v2 and later model comparisons, read [RESULTS.md](../RESULTS.md).

## Rebuild the presentation

The lockfile keeps the original PptxGenJS major version and overrides its image-size dependency with a patched release. Older image-size releases have a [parser denial-of-service vulnerability](https://github.com/advisories/GHSA-w3rx-r6r6-pgpr).

With Node.js and npm installed, run from the repository root:

```bash
npm ci --prefix report/deck
npm run build --prefix report/deck
```

The command writes `report/LLM_Markets_Presentation.pptx`. To build a separate copy, pass an output path (relative to `report/deck/` when using `npm run`):

```bash
npm run build --prefix report/deck -- ../../outputs/local/presentation.pptx
```

Create the destination directory first. The report and slides retain the original v1 wording; [reproducibility notes](../docs/reproducibility.md) record later audit findings.
