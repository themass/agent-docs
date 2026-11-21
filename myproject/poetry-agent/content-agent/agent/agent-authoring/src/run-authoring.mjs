#!/usr/bin/env node
import { readBase } from './base-reader.mjs';
import { makeProposal } from './draft-proposal.mjs';
import { compileGate } from './compiler-gate.mjs';
import { submitDraft } from './draft-submit.mjs';

const argv = process.argv.slice(2);
const get = (name) => { const i = argv.indexOf(`--${name}`); return i >= 0 ? argv[i + 1] : null; };
const work = get('work');
if (!work) { console.error('usage: node src/run-authoring.mjs --work <work-id> [--version <id>] [--bundle <path> --facts <path>] [--submit --api <url>]'); process.exit(2); }
const base = readBase(work, get('version'));
let proposal = makeProposal(base);
proposal.compile_result = compileGate({ bundlePath: get('bundle'), factsPath: get('facts') });
if (argv.includes('--submit')) proposal.submission = await submitDraft(proposal, get('api'));
console.log(JSON.stringify({ contract: 'controlled-authoring-v1', proposal }, null, 2));
