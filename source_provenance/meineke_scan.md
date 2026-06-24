# Meineke Scan Provenance

This repository deliberately does not track the rendered Meineke page images.
They are generated OCR inputs and can be recreated from the source PDF below.

## Source

- Work: Stephani Byzantii Ethnicorum quae supersunt
- Editor: August Meineke
- Publication: Berlin, G. Reimer, 1849
- Internet Archive item: https://archive.org/details/bub_gb_sZs-AAAAcAAJ
- PDF download: https://archive.org/download/bub_gb_sZs-AAAAcAAJ/bub_gb_sZs-AAAAcAAJ.pdf
- Google Books source recorded by Internet Archive: http://books.google.com/books?id=sZs-AAAAcAAJ&hl=&source=gbs_api
- Rights marker: https://creativecommons.org/publicdomain/mark/1.0/

## Local PDF Checked

- Local path at cleanup time: `/Users/gregb/Downloads/Meineke_Stephanos_Ethnika.pdf`
- SHA-256: `764f58c80fc59f3537c46f5db99a86979729ba512497e2dc14219b72d4b59c52`
- Size: `33226094` bytes
- PDF title: `Ethnica`
- Pages: `848`
- Page size: `183 x 300 pt`

The historical generated image corpus used files named
`pdf_pages_meineke/meineke_page_014.jpg` through
`pdf_pages_meineke/meineke_page_848.jpg`, inclusive. These are PDF pages 14-848
rendered as 300 DPI JPEGs for OCR queueing. The live PostgreSQL OCR queue also
stores these bytes in `images.image_data` for rows where
`source_document = 'meineke'`.

## Regeneration

Install Poppler so `pdftoppm` is available, then run:

```sh
mkdir -p pdf_pages_meineke
PDF=/Users/gregb/Downloads/Meineke_Stephanos_Ethnika.pdf
for page in $(seq 14 848); do
  out="pdf_pages_meineke/meineke_page_$(printf '%03d' "$page")"
  pdftoppm -jpeg -r 300 -f "$page" -l "$page" -singlefile "$PDF" "$out"
done
```

The regenerated JPEGs may not be byte-identical to the historical files because
JPEG encoders and defaults vary, but rendering the checked PDF at 300 DPI
matches the historical page numbering and dimensions used by the OCR pipeline.
