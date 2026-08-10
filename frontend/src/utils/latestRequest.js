/** 请求序号守卫：每次 begin() 递增序号，只有最新序号才被 isLatest 认可，防止旧响应覆盖新结果 */
export function createLatestRequestGuard() {
  let sequence = 0
  return {
    begin() { sequence += 1; return sequence },
    isLatest(token) { return token === sequence },
    invalidate() { sequence += 1 },
  }
}
