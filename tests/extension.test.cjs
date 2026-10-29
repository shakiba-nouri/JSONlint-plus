const test = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');

test('extension publishes diagnostics, quick fixes and AST for a JSON document', async () => {
  const callbacks = {}, commands = {}, reported = [];
  let provider, opened;
  let source = '{"age" 2}';
  const doc = { languageId: 'json', version: 1, isClosed: false, uri: { toString: () => 'file:///sample.json' }, lineCount: 1,
    getText: () => source, lineAt: () => ({ text: source }), positionAt: n => new Position(0,n) };
  class Position { constructor(line, character) { this.line=line; this.character=character; } }
  class Range { constructor(start,end) { this.start=start; this.end=end; } }
  class Diagnostic { constructor(range,message,severity) { Object.assign(this,{range,message,severity}); } }
  class WorkspaceEdit { replace(uri,range,text) { this.replacement={uri,range,text}; } }
  class CodeAction { constructor(title,kind) { this.title=title; this.kind=kind; } }
  const collection = { set: (uri,ds) => reported.push(ds), delete: () => {}, dispose: () => {} };
  const vscode = { Position, Range, Diagnostic, WorkspaceEdit, CodeAction, DiagnosticSeverity: {Error:0}, CodeActionKind:{QuickFix:'quickfix'}, ViewColumn:{Beside:2},
    Uri:{file: fsPath => ({fsPath})},
    window:{activeTextEditor:{document:doc}, createOutputChannel:()=>({appendLine:()=>{},dispose:()=>{}}), showErrorMessage:msg=>{throw Error(msg)}, showInformationMessage:()=>{}, showTextDocument:()=>Promise.resolve()},
    languages:{createDiagnosticCollection:()=>collection, registerCodeActionsProvider:(selector,p)=>{provider=p;return {dispose(){}};}},
    commands:{registerCommand:(name,fn)=>{commands[name]=fn;return {dispose(){}};}},
    workspace:{textDocuments:[doc], getConfiguration:()=>({get:key=>key==='pythonPath'?process.env.JSONLINT_TEST_PYTHON:''}),
      onDidOpenTextDocument:fn=>(callbacks.open=fn,{dispose(){}}), onDidChangeTextDocument:fn=>(callbacks.change=fn,{dispose(){}}), onDidCloseTextDocument:fn=>({dispose(){}}), onDidChangeConfiguration:fn=>({dispose(){}}),
      openTextDocument:arg=>{opened=arg;return Promise.resolve(arg);}}
  };
  const original=Module._load;
  Module._load=function(request,...args){return request==='vscode'?vscode:original.call(this,request,...args)};
  let extension; try { extension=require('../extension.js'); } finally { Module._load=original; }
  const context={extensionPath:path.resolve(__dirname,'..'),subscriptions:[]};
  extension.activate(context);
  for(let i=0;i<100 && !reported.length;i++) await new Promise(resolve=>setTimeout(resolve,30));
  assert.equal(reported.length,1);
  assert.equal(reported[0].length,1);
  assert.match(reported[0][0].message,/Expected ':'/);
  const actions=provider.provideCodeActions(doc,null,{diagnostics:reported[0]});
  assert.equal(actions[0].edit.replacement.text,': ');
  assert.equal(actions[0].edit.replacement.range.start.character,7);
  assert.ok(commands['jsonlintPlus.showAst']);
  assert.ok(commands['jsonlintPlus.showTokens']);
  source = '{"age": 2}'; doc.version++;
  callbacks.change({document:doc});
  for(let i=0;i<100 && reported.length < 2;i++) await new Promise(resolve=>setTimeout(resolve,30));
  assert.equal(reported[1].length, 0);
  commands['jsonlintPlus.showAst']();
  assert.equal(JSON.parse(opened.content).type, 'object');
  commands['jsonlintPlus.showTokens']();
  assert.equal(JSON.parse(opened.content)[0].type, 'LBRACE');
  context.subscriptions.forEach(sub=>sub.dispose?.());
});
