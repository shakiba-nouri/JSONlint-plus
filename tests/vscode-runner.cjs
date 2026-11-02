const vscode = require('vscode');
const assert = require('assert');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
exports.run = async function () {
  const extension = vscode.extensions.getExtension('shakiba-nouri.jsonlint-plus');
  assert.ok(extension, 'development extension is available');
  await extension.activate();
  const doc = await vscode.workspace.openTextDocument({language:'json',content:'{"a" 1}'});
  await vscode.window.showTextDocument(doc);
  let diagnostics = [];
  for(let i=0;i<100;i++) {
    diagnostics = vscode.languages.getDiagnostics(doc.uri).filter(d=>d.source==='JSONLint+');
    if(diagnostics.length) break;
    await sleep(100);
  }
  assert.ok(diagnostics.some(d=>d.message.includes("Expected ':'")), 'diagnostic is published');
  const actions = await vscode.commands.executeCommand('vscode.executeCodeActionProvider', doc.uri, diagnostics[0].range, 'quickfix');
  const fix = actions.find(a=>a.title==='Insert missing colon');
  assert.ok(fix && fix.edit, 'quick fix available');
  assert.ok(await vscode.workspace.applyEdit(fix.edit));
  for(let i=0;i<100;i++) {
    diagnostics = vscode.languages.getDiagnostics(doc.uri).filter(d=>d.source==='JSONLint+');
    if(!diagnostics.length) break;
    await sleep(100);
  }
  assert.equal(diagnostics.length,0);
  await vscode.commands.executeCommand('jsonlintPlus.showAst');
  await sleep(300);
  assert.ok(vscode.window.activeTextEditor.document.getText().includes('"type": "object"'));
  await vscode.window.showTextDocument(doc);
  await vscode.workspace.getConfiguration('editor', {languageId: 'json'}).update('defaultFormatter', 'shakiba-nouri.jsonlint-plus', vscode.ConfigurationTarget.Global, true);
  await vscode.commands.executeCommand('editor.action.formatDocument');
  await sleep(200);
  assert.match(doc.getText(), /\r?\n\s+"a": 1\r?\n/, 'formatting provider runs');
};
