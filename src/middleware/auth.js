const { USERS } = require("../data/mock");

const ROLES = { user: 0, head: 1, admin: 2 };

function auth(req, res, next) {
    const userId = Number(req.header("x-user-id") || 1);
    const user = USERS.find(u => u.id === userId);
    if (!user || user.blocked) {
        return res.status(401).json({ code: "401", message: "Нет авторизации" });
    }
    req.user = user;
    next();
}

function requireRole(minRole) {
    return (req, res, next) => {
        if (ROLES[req.user.role] < ROLES[minRole]) {
            return res.status(403).json({ code: "403", message: "Нет доступа" });
        }
        next();
    };
}

module.exports = { auth, requireRole, ROLES };