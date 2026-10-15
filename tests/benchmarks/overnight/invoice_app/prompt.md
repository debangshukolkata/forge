Build a web application for invoice OCR and data entry support.

BACKGROUND
Today a person in charge opens each supplier invoice, reads the values from its fields and types them into an ERP screen. The application should do the reading, so the person only checks and corrects.

WHAT THE APPLICATION MUST DO (three screens plus a report)

1. Data ingestion screen
- Invoices come in from an email mailbox (IMAP) or from a SharePoint document library (Microsoft Graph), or by upload on this screen (several files at once, drag and drop, PDF, PNG and JPG).
- Show each source as a connection with its settings, a "Test connection" and a "Sync now" action, its last sync time and what it fetched. You cannot reach a real mailbox or SharePoint from this machine: build both connectors behind one interface, make the settings screen real (host, folder, credentials are read from environment variables and never stored or shown), and include a clearly labelled DEMO mode in which a local folder stands in for the mailbox and for the document library, so the whole flow can be shown. Say honestly in the interface and in the README what is real and what is demo.
- Show an ingestion log: what arrived, from where, when, and any file that could not be read.

2. Invoices screen
- A list of invoices in two groups: unprocessed and processed (and within processed: needs review, approved). Search, filter by supplier, date and status, sort.
- Batch processing: select several invoices and process them at once, with visible progress. Manual processing: open one invoice and process it on its own.
- Processing reads the invoice: use the PDF text layer when there is one and Tesseract OCR when there is not (Tesseract is installed on this machine; find it, and make its path configurable). Extract: supplier name, invoice number, invoice date, due date, purchase order number, currency, subtotal, tax, total, and the line items (description, quantity, unit price, amount). Give every field a confidence value and the position where it was found on the page.

3. Review screen (opened from the list)
- The original invoice is shown on the left (page images, zoom, page navigation). On the right is a form of the same fields with the extracted values, side by side so the person can compare them at a glance. Selecting a field highlights where it was found on the invoice.
- Fields with low confidence or failed checks (line items do not add up to the subtotal, subtotal plus tax is not the total, a date is impossible) are flagged.
- The person can correct any value and then approve. Corrections are stored with the original extraction so the reporting can show what had to be corrected. Next and previous invoice, and a clear state (unprocessed, needs review, approved).
- Approved invoices can be exported for the ERP as CSV and JSON.

4. Reporting
- Invoices received, processed and approved over time; value by supplier and by month; how many fields were corrected and which fields are corrected most often (accuracy of the extraction); processing time; a table that can be exported as CSV.

REQUIREMENTS
- Python 3.13 with FastAPI and Jinja2 templates, SQLite for storage, plain JavaScript and CSS in the pages. No Node or build step. Install what you need into this project's own environment. One command starts it (for example python -m app) and the README says how.
- Create about ten fictional sample invoices yourself with different layouts and suppliers (some PDFs with a text layer, some scanned-looking images so the OCR path is exercised), with the true values written down in a file, and use them to test the extraction: write pytest tests that compare the extracted values with the true values and report the accuracy per field. Do not use any real personal or company data.
- The application must look designed, not like a default admin template: decide what it should feel like for the person who checks invoices all day, and let that drive the look. It works from desktop width down to a laptop screen. The review screen is where it is won or lost.
- Look at every screen in a browser at desktop width before you finish, fix what you see, and finish with a short summary of what is real, what is demo, and how well the extraction did on the samples.
