const XLSX = require("excel4node");
const PDFDocument = require("pdfkit");
const { Parser } = require("json2csv");

const COLUMN_MAP = {
    name: { title: "Вуз", get: v => v.name },
    direction: { title: "Направление", get: v => v.direction },
    product: { title: "Продукт", get: v => v.product },
    stage: { title: "Статус", get: v => v.stage },
    manager: { title: "Ответственный", get: v => v.manager }
};

function pickColumns(keys) {
    return keys.filter(k => COLUMN_MAP[k]).map(k => ({ key: k, ...COLUMN_MAP[k] }));
}

function toXlsx(rows, columns, res) {
    const wb = new XLSX.Workbook();
    const ws = wb.addWorksheet("Отчёт");
    columns.forEach((c, i) => {
        ws.cell(1, i + 1).string(c.title).style({ bold: true });
    });
    rows.forEach((row, r) => {
        columns.forEach((c, i) => {
            ws.cell(r + 2, i + 1).string(String(c.get(row) ?? ""));
        });
    });
    res.setHeader("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    res.setHeader("Content-Disposition", "attachment; filename=report.xlsx");
    wb.write("report.xlsx", res);
}

function toCsv(rows, columns, res) {
    const fields = columns.map(c => ({ label: c.title, value: c.get }));
    const parser = new Parser({ fields });
    const csv = parser.parse(rows);
    res.setHeader("Content-Type", "text/csv; charset=utf-8");
    res.setHeader("Content-Disposition", "attachment; filename=report.csv");
    res.send("\uFEFF" + csv);
}

function toPdf(rows, columns, res) {
    const doc = new PDFDocument({ margin: 30, size: "A4" });
    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", "attachment; filename=report.pdf");
    doc.pipe(res);

    doc.fontSize(16).text("Отчёт по вузам", { underline: true });
    doc.moveDown();

    rows.forEach((row, i) => {
        doc.fontSize(11).text(
            `${i + 1}. ` + columns.map(c => `${c.title}: ${c.get(row)}`).join(" | ")
        );
        doc.moveDown(0.3);
    });

    doc.end();
}

function build(rows, columns, format, res) {
    if (format === "pdf") return toPdf(rows, columns, res);
    if (format === "xls" || format === "xlsx") return toXlsx(rows, columns, res);
    return toCsv(rows, columns, res);
}

module.exports = { pickColumns, build, COLUMN_MAP };