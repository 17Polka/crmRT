const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.json());
const universitiesRoutes = require("./routes/universities");
app.use("/api/universities", universitiesRoutes);
const workflowRoutes = require("./routes/workflow");
app.use("/api/workflow", workflowRoutes);
const reportsRoutes = require("./routes/reports");
app.use("/api/reports", reportsRoutes);

app.get("/health", (req, res) => {
    res.json({ status: "ok", time: new Date() });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`API on http://localhost:${PORT}`));