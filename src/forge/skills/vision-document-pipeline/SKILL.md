---
name: vision-document-pipeline
description: Build a pipeline that reads documents/images (OCR, handwriting, forms, signatures, boxes) with a vision LLM: preprocessing, structured output, confidence, evals.
---
# Vision / document pipelines (spec §13A.6)

1. Input handling: accept images and PDFs (render PDF pages to images at ~200 DPI). Normalise orientation,
   keep the original; never store copies outside the app's own folders.
2. Ask the vision model for STRUCTURED output (JSON schema): fields with values, bounding boxes in pixel
   coordinates of the original image, and a confidence per field. Validate the JSON; retry once on errors.
3. Locating regions (a signature, a stamp, a diagram): do NOT trust boxes from a GPT-class vision model alone —
   measured on a clean synthetic page its signature box had zero overlap with the truth, while it read the text
   perfectly. Use the hybrid (spec §13A.6): classical CV proposes candidates (Pillow/OpenCV: binarise, find
   connected ink components, merge nearby ones into blobs, drop printed text lines by their regular height and
   long horizontal extent), then send each candidate CROP to the model ("is this a handwritten signature? yes/no +
   confidence") or send the page with numbered candidate boxes drawn on it and ask which number; keep the
   winner's CV box, pad it a few pixels, crop from the ORIGINAL image, save as PNG and report box + confidence.
   If no candidate qualifies, say so — never invent a box.
4. Handwriting: prefer the model's reading plus a confidence; flag low-confidence fields for human review.
5. Retrieval (RAG over documents): index text chunks AND image-derived descriptions with metadata (file, page,
   box); answer with citations to file/page.
6. Sensitive documents (prescriptions, IDs): keep them local, don't log their content, send them only to the
   configured model endpoint, and don't cache model outputs outside the app's data folder.
7. Measure: a small labelled eval set (boxes + field values), metrics IoU >= 0.5 for boxes and exact/normalised
   field match; iterate against the eval, not against a single example.
