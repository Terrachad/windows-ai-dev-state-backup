# Brand assets

`banner.svg` is the editable, self-contained source. `social-preview.png` is the
1280 × 640 pixel export for GitHub's repository social preview setting.

The artwork uses generic folder/verification shapes, not OpenAI, Anthropic or
GitHub logos. It does not imply endorsement. Text remains readable without the
illustration; the SVG includes a title and accessible description.

Colors: midnight `#111c2f`, near-black `#070d19`, mint `#64e7c4`, off-white `#f7f9fd`.
Font stack: system DejaVu Sans / sans-serif; no font files are bundled.

To regenerate with optional maintainer-only CairoSVG installed:

```powershell
py -3 -c "import cairosvg; cairosvg.svg2png(url='assets/banner.svg', write_to='assets/social-preview.png')"
```

The runtime does not depend on CairoSVG. Update release wording in both assets
when the release status changes. Upload the PNG manually in the repository's
Settings → General → Social preview; publishing the image as a source file does
not automatically activate that setting.
