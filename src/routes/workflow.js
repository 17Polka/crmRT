const express = require("express");
const router = express.Router();
const { UNIVERSITIES, STAGES } = require("../data/mock");

// POST /api/workflow/:id/next  body: { comment, managerId }
// POST /api/workflow/:id/prev
router.post("/:id/:dir", (req, res) => {
    const v = UNIVERSITIES.find(x => x.id === Number(req.params.id));
    if (!v) return res.status(404).json({ code: "404", message: "Вуз не найден" });

    const delta = req.params.dir === "next" ? 1 : -1;
    const next = v.stageIndex + delta;

    if (next < 0 || next >= STAGES.length) {
        return res.status(400).json({ code: "400", message: "Этап вне диапазона" });
    }
    if (delta < 0 && !req.body.comment) {
        return res.status(400).json({ code: "400", message: "Комментарий обязателен при возврате" });
    }

    const old = v.stageIndex;
    v.stageIndex = next;
    v.lastUpdate = new Date().toLocaleDateString("ru");
    v.history.unshift({
        text: `${STAGES[old]} → ${STAGES[next]}` + (req.body.comment ? `. ${req.body.comment}` : ""),
        date: v.lastUpdate
    });
    if (req.body.comment) {
        v.comments.push({
            user: req.body.userName || "Тест 1",
            date: v.lastUpdate,
            text: req.body.comment
        });
    }

    res.json({ ok: true, university: v });
});

module.exports = router;