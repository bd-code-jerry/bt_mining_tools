export function createWorkspaceDataController(fetchWorkspaceData, onStateChange = () => {}) {
  let requestNumber = 0;
  let currentState = { workspace: null, data: null, loading: false, error: null };

  const publish = (nextState) => {
    currentState = nextState;
    onStateChange(currentState);
  };

  return {
    get state() {
      return currentState;
    },

    async switchTo(workspace) {
      const thisRequest = ++requestNumber;
      publish({ ...currentState, loading: true, error: null });
      try {
        const data = await fetchWorkspaceData(workspace);
        if (thisRequest !== requestNumber) return false;
        publish({ workspace, data, loading: false, error: null });
        return true;
      } catch (error) {
        if (thisRequest !== requestNumber) return false;
        publish({ ...currentState, loading: false, error });
        return false;
      }
    },
  };
}
