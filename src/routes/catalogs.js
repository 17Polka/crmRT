const express = require("express");
const router = express.Router();
const { UNIVERSITIES, DIRECTIONS, PRODUCTS, USERS } = require("../data/mock");
const { auth, requireRole } = require("../middleware/auth");

router.get("/", (req, res) => {
  res.json({
    universities: UNIVERSITIES.map(v => ({ id: v.id, name: v.name, city: v.city })),
    directions: DIRECTIONS,
    products: PRODUCTS,
    managers: USERS.map(u => ({ id: u.id, name: u.name, role: u.role }))
  });
});

router.post("/import", auth, requireRole("admin"), (req, res) => {
  res.json({ ok: true, message: "Импорт выполнен (демо)" });
});

module.exports = router;