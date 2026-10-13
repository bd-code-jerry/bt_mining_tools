export function createLatestLoader(fetchData, commit) {
  let sequence = 0;
  return { invalidate() { sequence += 1; }, async load(...args) { const current=++sequence; try { const data=await fetchData(...args); if(current!==sequence) return false; commit(data); return true; } catch(error) { if(current!==sequence) return false; throw error; } } };
}
