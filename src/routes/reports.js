const express = require("express");
const router = express.Router();
const { UNIVERSITIES, STAGES, DIRECTIONS, PRODUCTS, USERS } = require("../data/mock");
const { pickColumns, build } = require("../services/reportService");
const { auth } = require("../middleware/auth");

router.use(auth);

// POST /api/reports
// body: { periodFrom, periodTo, directionId, productId, managerId, columns:[], format:"xlsx" }
router.post("/", (req, res) => {
  const { periodFrom, periodTo, directionId, productId, managerId, columns, format } = req.body;

  let list = req.user.role === "user"
    ? UNIVERSITIES.filter(v => v.managerId === req.user.id)
    : [...UNIVERSITIES];

  if (periodFrom || periodTo) {
    const from = periodFrom ? new Date(periodFrom.split(".").reverse().join("-")) : null;
    const to   = periodTo   ? new Date(periodTo.split(".").reverse().join("-"))   : null;
    list = list.filter(v => {
      const d = new Date(v.lastUpdate.split(".").reverse().join("-"));
      if (from && d < from) return false;
      if (to && d > to) return false;
      return true;
    });
  }

  if (directionId) list = list.filter(v => v.directionId === Number(directionId));
  if (productId)   list = list.filter(v => v.productId === Number(productId));
  if (managerId)   list = list.filter(v => v.managerId === Number(managerId));

  const enriched = list.map(v => ({
    ...v,
    direction: DIRECTIONS.find(d => d.id === v.directionId)?.name,
    product: PRODUCTS.find(p => p.id === v.productId)?.name,
    manager: USERS.find(u => u.id === v.managerId)?.name,
    stage: STAGES[v.stageIndex]
  }));

  const cols = pickColumns(
    columns && columns.length
      ? columns
      : ["name", "direction", "product", "stage", "manager"]
  );

  build(enriched, cols, format || "xlsx", res);
});

module.exports = router;