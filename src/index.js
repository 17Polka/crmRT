const express = require("express");
const cors = require("cors");

const universitiesRoutes = require("./routes/universities");
const workflowRoutes = require("./routes/workflow");
const reportsRoutes = require("./routes/reports");
const catalogsRoutes = require("./routes/catalogs");
const integrationsRoutes = require("./routes/integrations");

const app = express();
app.use(cors());
app.use(express.json());

app.get("/health", (req, res) => {
  res.json({ status: "ok", time: new Date() });
});

app.use("/api/universities", universitiesRoutes);
app.use("/api/workflow", workflowRoutes);
app.use("/api/reports", reportsRoutes);
app.use("/api/catalogs", catalogsRoutes);
app.use("/api/integrations", integrationsRoutes);

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`API on http://localhost:${PORT}`));