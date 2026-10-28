// Download list: documents as rows between hairlines, each with its title, a one-line description, the file type and size, and a download link whose text
// says what it is. Use it for forms, reports, price lists and policies. Give the real size and type (the audit flags nothing here, readers do); a link to a
// PDF should say PDF. `href` points at the file; the `download` attribute is set so the browser saves it.
export type DownloadItem = { title: string; text: string; type: string; size: string; href: string };

export default function DownloadList({
  eyebrow = "Documents",
  title = "Forms and reports.",
  items = [
    { title: "Membership application form", text: "Fill in by hand or on screen; return it to the office.", type: "PDF", size: "180 KB", href: "#membership-form.pdf" },
    { title: "Annual report 2025", text: "Accounts, activities and what we plan for next year.", type: "PDF", size: "2.4 MB", href: "#annual-report-2025.pdf" },
    { title: "Price list, January 2026", text: "Every class and room, with the hourly rates.", type: "Spreadsheet", size: "42 KB", href: "#price-list.xlsx" },
    { title: "Safeguarding policy", text: "How we keep children and vulnerable adults safe.", type: "Word", size: "96 KB", href: "#safeguarding-policy.docx" },
  ],
}: {
  eyebrow?: string;
  title?: string;
  items?: DownloadItem[];
}) {
  return (
    <section className="mx-auto max-w-4xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold sm:text-4xl">{title}</h2>
      <ul className="mt-10 border-y border-ink-900">
        {items.map((item) => (
          <li key={item.href} className="grid items-center gap-x-6 gap-y-2 border-b border-ink-200 py-5 last:border-b-0 md:grid-cols-[1fr_auto]">
            <div>
              <h3 className="text-lg font-semibold">{item.title}</h3>
              <p className="mt-1 text-ink-700">{item.text}</p>
            </div>
            <a href={item.href} download className="btn-secondary justify-self-start md:justify-self-end">
              Download {item.type}
              <span className="font-normal text-ink-500">{item.size}</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
