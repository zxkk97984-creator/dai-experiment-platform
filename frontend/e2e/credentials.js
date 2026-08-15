// E2E 登录凭据：环境变量可覆盖默认值（如 CI 使用独立账号库时）。
// 默认取 scripts/seed_e2e.py 种子的 teacher / Passw0rd!，CI E2E job 与本地 e2e 栈共用。
const TEACHER_USER = process.env.E2E_TEACHER_USER || 'teacher'
const TEACHER_PASS = process.env.E2E_TEACHER_PASS || 'Passw0rd!'

export { TEACHER_USER, TEACHER_PASS }
