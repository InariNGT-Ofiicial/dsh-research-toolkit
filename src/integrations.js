// Only inspect tools visible to the calling agent. External calls retain their
// own tool names, execution pipeline and native DSH policy checks.
export const COMPANIONS = Object.freeze([
  { id: 'matlab-mcp', title: 'MATLAB MCP / Simulink',
    repository: 'https://github.com/lovedheart/dsh-matlab-mcp-plugin',
    serverRepository: 'https://github.com/matlab/matlab-mcp-server',
    match: (name) => name.startsWith('mcp__matlab__'),
    use: 'Interactive MATLAB evaluation, script/test execution and static analysis. Simulink requires separately registered model_* tools and the licensed toolkit.',
    fallback: 'Use research_compile/research_run for existing MATLAB jobs.' },
  { id: 'zotero', title: 'Zotero literature tools',
    repository: 'https://github.com/Hongcheng-LI/dsh-zotero',
    match: (name) => name.startsWith('zotero_'),
    use: 'Collections, richer search, metadata, notes, local PDF fulltext and attachment access. Writes require a user-requested operation.',
    fallback: 'Use existing Zotero search/item/children jobs through research_run.' },
]);

export function integrationSnapshot(tools, agent) {
  const schemas = typeof tools.schemas === 'function' ? tools.schemas(agent) : [];
  return {
    status: 'passed',
    boundary: 'Visible tool registration only; availability does not prove server connection, license, application execution or successful acceptance.',
    integrations: COMPANIONS.map(({ match, ...entry }) => {
      const visible = schemas.filter((s) => match(s.name));
      return { ...entry, status: visible.length ? 'tools_registered' : 'not_registered',
        tools: visible.map((s) => ({ name: s.name, description: s.description ?? '', parameters: s.parameters })),
        application_verified: false };
    }),
  };
}
