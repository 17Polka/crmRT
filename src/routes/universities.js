const express = require("express");
const router = express.Router();
const { UNIVERSITIES, STAGES, DIRECTIONS, PRODUCTS, USERS } = require("../data/mock");

// GET /api/universities?direction=1&product=1&stage=3&manager=2&q=текст
router.get("/", (req, res) => {
    let list = [...UNIVERSITIES];
    const { direction, product, stage, manager, q } = req.query;

    if (direction) list = list.filter(v => v.directionId === Number(direction));
    if (product) list = list.filter(v => v.productId === Number(product));
    if (stage) list = list.filter(v => v.stageIndex === Number(stage));
    if (manager) list = list.filter(v => v.managerId === Number(manager));
    if (q) {
        const s = String(q).toLowerCase();
        list = list.filter(v => (v.name + v.city).toLowerCase().includes(s));
    }

    const enriched = list.map(v => ({
        ...v,
        direction: DIRECTIONS.find(d => d.id === v.directionId)?.name,
        product: PRODUCTS.find(p => p.id === v.productId)?.name,
        manager: USERS.find(u => u.id === v.managerId)?.name,
        stage: STAGES[v.stageIndex]
    }));

    res.json({ total: enriched.length, items: enriched });
});

// GET /api/universities/:id
router.get("/:id", (req, res) => {
    const v = UNIVERSITIES.find(x => x.id === Number(req.params.id));
    if (!v) return res.status(404).json({ code: "404", message: "Вуз не найден" });
    res.json(v);
});

module.exports = router;