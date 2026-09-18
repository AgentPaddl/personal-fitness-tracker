# Public benchmark assets

Prepared 2026-09-18 for the [18-case manifest](../gpt54-mini-benchmark.v1.json).
No model has evaluated these fixtures. These are six photographic test inputs
derived from **three source photos**, not six independent meals. P1/P4/P6 and
P2/P3 are correlated. P5 is a non-food control. L1/L2 are separately rendered
synthetic labels. All sources were visually reviewed: no people, personal
records or identifying private backgrounds; P5 contains product branding.

## Sources and attribution

| Key | Source, author and license | Derived assets |
| --- | --- | --- |
| rice | [A bowl of rice.jpg](https://commons.wikimedia.org/wiki/File:A_bowl_of_rice.jpg), Douglas Perkins, [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) | P1, P4, P6 |
| muesli | [Muesli with Berries.jpg](https://commons.wikimedia.org/wiki/File:Muesli_with_Berries.jpg), David Stewart, [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) | P2, P3 |
| stapler | [Evo paper pro stapler open.jpg](https://commons.wikimedia.org/wiki/File:Evo_paper_pro_stapler_open.jpg), Nashucks, [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) | P5 |

P2 and P3 retain CC BY 2.0 attribution and license. Changes are described below;
no source author endorsement is implied. Preserve this attribution when sharing
the fixtures. Copyright licenses do not grant trademark endorsement.

Original downloads (not included; verified before processing):

| Local source filename | Original URL | SHA-256 |
| --- | --- | --- |
| pft-benchmark-rice.jpg | https://upload.wikimedia.org/wikipedia/commons/d/d6/A_bowl_of_rice.jpg | a68b087e328255f6103af4e3a954beb833c8564721c3bf9b65a35a75f479100f |
| pft-benchmark-muesli.jpg | https://upload.wikimedia.org/wikipedia/commons/9/90/Muesli_with_Berries.jpg | 38448fd7599581f9286ed8de35fe6e082953e2c962f55a85f7c7a2e4ba45b3ea |
| pft-benchmark-stapler.jpg | https://upload.wikimedia.org/wikipedia/commons/d/d7/Evo_paper_pro_stapler_open.jpg | 4c07ad20a49e9894aab092939706437b4432f4909e355708f8b950c4aa429396 |

## Transformations

The offline [preparer](prepare_assets.py) verifies original hashes, applies EXIF
orientation, converts RGB, thumbnails to 1000x1000 with Lanczos and re-encodes
JPEG quality 90 without metadata. Coordinates below refer to this resized image.

| Asset | Changes | Dimensions |
| --- | --- | --- |
| P1.jpg | Rice, resize only | 1000x883 |
| P2.jpg | Muesli, resize only; separate glass is explicitly excluded by the case | 1000x665 |
| P3.jpg | Muesli, brightness multiplied by 0.45; right half replaced by RGB(50,50,50) | 1000x665 |
| P4.jpg | Rice, crop rectangle (250,200,750,700), no new scale cue | 500x500 |
| P5.jpg | Stapler, resize only | 1000x458 |
| P6.jpg | Rice, white instruction overlay, text from the preparer; an artificial robustness case, not a photographed note | 1000x883 |
| L1.png / L2.png | Locally rendered declared label text, white RGB canvas, bundled Pillow default font size 30 | 800x500 |

Frozen output hashes and dimensions are in the manifest. All files are below
3 MiB and 1024 pixels per side, with no EXIF. They are ordinary licensed fixture
data, not logs. Reproduction used Python 3.13.15 and Pillow 12.3.0; other codec or
font versions may change encoded bytes. Use the frozen assets for the approved
run, never silently regenerate and accept a different hash. From `ai-gateway/`:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tests/fixtures/gpt54-mini-assets/prepare_assets.py /path/to/verified/downloads
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_pilot.py -k benchmark
```

## Nutrition references and uncertainty

- T1/T2/T5 declare per-100-g nutrition in their own input. Their references are
  arithmetic fixtures, not nutrition-database claims: rice 150 g multiplies by
  1.5; yogurt 200 g plus oats 40 g uses 2.0 and 0.4 respectively.
- R1-R4 use the fixed 200 g rice baseline in the manifest, not the public photo
  or a previous model response. R3/R4's image origin is synthetic; no photo is
  attached. Oil in R2 has an explicit 90 kcal/10 g fat declaration.
- L1 and L2 multiply the declared label values by 1.5. Synthetic label energy
  need not be recomputed from rounded macronutrients using 4/4/9.
- P1/P4/P6 show cooked rice, but portion mass, water content, variety and added
  fat are unknown. No calorie or macro target is assigned.
- P2/P3 show cereal flakes, berries and a yogurt-like topping. Exact ingredients,
  milk/yogurt fat level, added sugar, quantities and consumption are unknown.
  The separate glass is not part of the requested meal. No numeric target exists.
- P3 is digital degradation, not evidence from a naturally occluded meal. P4
  removes portion context. P6 tests resistance to visible instructions.
- P5 must not become a confidently invented meal. A generic provider failure
  alone does not establish successful recognition of a non-food object.

Human review scores recognition, task adherence and expressed assumptions or
uncertainty. There is **no photo calorie-accuracy percentage** for this set.
Exact photo nutrition validation still needs nonprivate weighed recipes, recorded
raw/cooked edible weights, ingredient labels/composition sources and preparation
loss/added-fat information. These are missing evidence for a later accuracy
study, not permission to infer hidden weights in this screening run.