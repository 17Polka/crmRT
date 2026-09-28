const express = require("express");
const router = express.Router();
const { auth } = require("../middleware/auth");

router.use(auth);

router.get("/lms", (req, res) => {
  res.json({ source: "LMS", items: [{ id: 1, name: "Поток 1", students: 25 }] });
});

router.get("/site", (req, res) => {
  res.json({ source: "Site", items: [{ id: 1, name: "Заявка с сайта" }] });
});

router.post("/sync", (req, res) => {
  res.json({ ok: true, syncedAt: new Date().toISOString() });
});

module.exports = router;