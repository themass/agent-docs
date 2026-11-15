import { deflateRawSync } from "node:zlib";

/**
 * Minimal valid files for the upload paths, generated at test time.
 *
 * Not committed as samples on purpose: a resume fixture is somebody's personal
 * data the moment it is realistic, and the intake pipeline only needs a
 * well-formed file to exercise storage, the parse-state row and the text
 * extraction path.
 */

/** A one-page PDF with a single line of text. */
export function minimalPdf(text: string): Buffer {
  const escaped = text.replace(/[()\\]/g, "");
  const content = `BT /F1 12 Tf 50 750 Td (${escaped}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((obj, i) => {
    offsets.push(pdf.length);
    pdf += `${i + 1} 0 obj\n${obj}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const off of offsets) pdf += `${String(off).padStart(10, "0")} 00000 n \n`;
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf, "latin1");
}

/** One stored (uncompressed) entry in a ZIP archive. */
function zipEntry(name: string, data: Buffer): Buffer {
  const crc = crc32(data);
  const local = Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50, 0); // local file header
  local.writeUInt16LE(20, 4); // version needed
  local.writeUInt16LE(0, 6); // flags
  local.writeUInt16LE(0, 8); // method: store
  local.writeUInt32LE(0, 10); // time/date
  local.writeUInt32LE(crc, 14);
  local.writeUInt32LE(data.length, 18);
  local.writeUInt32LE(data.length, 22);
  local.writeUInt16LE(name.length, 26);
  local.writeUInt16LE(0, 28);
  return Buffer.concat([local, Buffer.from(name, "utf8"), data]);
}

function crc32(buf: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of buf) {
    crc ^= byte;
    for (let i = 0; i < 8; i++) crc = crc & 1 ? (crc >>> 1) ^ 0xedb88320 : crc >>> 1;
  }
  return (crc ^ 0xffffffff) >>> 0;
}

/**
 * A minimal .docx: a ZIP with the three parts Word (and every text extractor)
 * insists on — `[Content_Types].xml`, the package relationships, and the body.
 */
export function minimalDocx(text: string): Buffer {
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const contentTypes =
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
    '<Default Extension="xml" ContentType="application/xml"/>' +
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>' +
    "</Types>";

  const rels =
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>' +
    "</Relationships>";

  const document =
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' +
    `<w:p><w:r><w:t xml:space="preserve">${esc}</w:t></w:r></w:p>` +
    "</w:body></w:document>";

  const parts: Array<[string, Buffer]> = [
    ["[Content_Types].xml", Buffer.from(contentTypes, "utf8")],
    ["_rels/.rels", Buffer.from(rels, "utf8")],
    ["word/document.xml", Buffer.from(document, "utf8")],
  ];
  const local = parts.map(([name, data]) => zipEntry(name, data));
  return Buffer.concat([...local, buildCentralDirectory(parts, local)]);
}

function buildCentralDirectory(
  parts: Array<[string, Buffer]>,
  local: Buffer[],
): Buffer {
  const rows: Buffer[] = [];
  // Each central row records where *its own local header* starts, counted from the
  // beginning of the file. The local headers are concatenated in order, so that
  // offset is the running sum of the previous entries' total sizes.
  let offset = 0;
  for (const [i, [name]] of parts.entries()) {
    // Read the header fields out of the *local header* that was just emitted —
    // `parts[i][1]` is the raw payload and has no such fields at those offsets.
    // Reading the payload here produced a CRC and length taken from the document
    // text, which is why Python's zipfile reported "Overlapped entries".
    const localHeader = local[i];
    const crc = localHeader.readUInt32LE(14);
    const dataLen = localHeader.readUInt32LE(18);
    const row = Buffer.alloc(46);
    row.writeUInt32LE(0x02014b50, 0); // central directory header
    row.writeUInt16LE(20, 4);
    row.writeUInt16LE(20, 6);
    row.writeUInt16LE(0, 8);
    row.writeUInt16LE(0, 10); // store
    row.writeUInt32LE(0, 12);
    row.writeUInt32LE(crc, 16);
    row.writeUInt32LE(dataLen, 20);
    row.writeUInt32LE(dataLen, 24);
    row.writeUInt16LE(name.length, 28);
    row.writeUInt16LE(0, 30);
    row.writeUInt16LE(0, 32);
    row.writeUInt16LE(0, 34);
    row.writeUInt16LE(0, 36);
    row.writeUInt32LE(0, 38);
    row.writeUInt32LE(offset, 42);
    rows.push(Buffer.concat([row, Buffer.from(name, "utf8")]));
    offset += local[i].length;
  }
  const dir = Buffer.concat(rows);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); // end of central directory
  end.writeUInt16LE(0, 4);
  end.writeUInt16LE(0, 6);
  end.writeUInt16LE(parts.length, 8);
  end.writeUInt16LE(parts.length, 10);
  end.writeUInt32LE(dir.length, 12);
  end.writeUInt32LE(offset, 16);
  end.writeUInt16LE(0, 20);
  return Buffer.concat([dir, end]);
}
