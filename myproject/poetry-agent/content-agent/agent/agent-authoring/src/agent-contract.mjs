export const AUTHORING_CONTRACT = Object.freeze({
  mode: 'controlled-authoring',
  reads: ['content', 'poemLines', 'versions', 'claims', 'backgrounds', 'bgLineLinks', 'annotations', 'coverage'],
  writes: ['DRAFT proposal'],
  forbidden: ['publish', 'retract', 'verify_source', 'set_verified', 'delete_content'],
  releaseAuthority: 'human-review'
});
