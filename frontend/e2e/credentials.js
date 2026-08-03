// E2E 登录凭据：环境变量可覆盖默认值（如 CI 使用独立账号库时）
const TEACHER_USER = process.env.E2E_TEACHER_USER || 'teacher_john'
const TEACHER_PASS = process.env.E2E_TEACHER_PASS || 'Test1234!'

export { TEACHER_USER, TEACHER_PASS }
