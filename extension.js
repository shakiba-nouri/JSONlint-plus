const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');

function activate(context) {
  const collection = vscode.languages.createDiagnosticCollection('JSONLint+');
  const output = vscode.window.createOutputChannel('JSONLint+');
  const timers = new Map();
  const processes = new Map();
  let reportedFailure = false;
  context.subscriptions.push(collection, output);

  function schedule(document) {
    const key = document.uri.toString();
    clearTimeout(timers.get(key));
    const running = processes.get(key);
    if (running) running.kill();
    if (document.languageId !== 'json') { collection.delete(document.uri); return; }
    timers.set(key, setTimeout(() => { timers.delete(key); validate(document); }, 250));
  }
  function validate(document) {
    const key = document.uri.toString();
    const version = document.version;
    const source = document.getText();
    const python = vscode.workspace.getConfiguration('jsonlintPlus', document.uri).get('pythonPath');
    const child = spawn(python, ['-m', 'jsonlint_plus.vscode_bridge'], {
      cwd: context.extensionPath,
      env: { ...process.env, PYTHONPATH: path.join(context.extensionPath, 'src') },
      windowsHide: true
    });
    processes.set(key, child);
    let stdout = '', stderr = '', failed = false;
    child.stdout.setEncoding('utf8'); child.stdout.on('data', data => stdout += data);
    child.stderr.setEncoding('utf8'); child.stderr.on('data', data => stderr += data);
    function report(message) {
      if (processes.get(key) !== child) return;
      failed = true; collection.delete(document.uri);
      output.appendLine(message);
      if (!reportedFailure) {
        reportedFailure = true;
        vscode.window.showErrorMessage('JSONLint+ could not run Python. Check JSONLint+: Python Path and the JSONLint+ output channel.');
      }
    }
    child.on('error', err => report(err.message));
    child.on('close', code => {
      if (processes.get(key) !== child) return;
      processes.delete(key);
      if (failed || document.isClosed || document.version !== version) return;
      if (code !== 0) { output.appendLine(stderr); collection.delete(document.uri); if (!reportedFailure) { reportedFailure = true; vscode.window.showErrorMessage('JSONLint+ analysis failed. See the JSONLint+ output channel.'); } return; }
      try {
        const result = JSON.parse(stdout);
        const diagnostics = result.diagnostics.map(item => {
          const line = Math.max(0, Math.min(item.line - 1, document.lineCount - 1));
          const lineText = document.lineAt(line).text;
          const character = Array.from(lineText).slice(0, item.column - 1).join('').length;
          const start = new vscode.Position(line, character);
          const end = new vscode.Position(line, Math.min(character + 1, lineText.length));
          const diagnostic = new vscode.Diagnostic(new vscode.Range(start, end), item.message, vscode.DiagnosticSeverity.Error);
          diagnostic.source = 'JSONLint+';
          if (item.fix) diagnostic.fix = item.fix;
          return diagnostic;
        });
        reportedFailure = false;
        collection.set(document.uri, diagnostics);
      } catch (err) { collection.delete(document.uri); output.appendLine(String(err)); vscode.window.showErrorMessage('JSONLint+ returned an invalid response. See the output channel.'); }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify({ text: source }));
  }
  context.subscriptions.push(vscode.languages.registerCodeActionsProvider({ language: 'json' }, {
    provideCodeActions(document, range, context) {
      return context.diagnostics.filter(d => d.source === 'JSONLint+' && d.fix).map(d => {
        const fix = d.fix;
        // Python offsets count Unicode code points; VS Code offsets count UTF-16 units.
        const chars = Array.from(document.getText());
        const start = chars.slice(0, fix.start).join('').length;
        const end = chars.slice(0, fix.end).join('').length;
        const action = new vscode.CodeAction(fix.title, vscode.CodeActionKind.QuickFix);
        action.edit = new vscode.WorkspaceEdit();
        action.edit.replace(document.uri, new vscode.Range(document.positionAt(start), document.positionAt(end)), fix.text);
        action.diagnostics = [d]; action.isPreferred = true;
        return action;
      });
    }
  }, { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }));
  context.subscriptions.push(vscode.workspace.onDidOpenTextDocument(schedule),
    vscode.workspace.onDidChangeTextDocument(event => schedule(event.document)),
    vscode.workspace.onDidCloseTextDocument(document => {
      const key = document.uri.toString(); clearTimeout(timers.get(key)); timers.delete(key);
      const child = processes.get(key); if (child) child.kill(); processes.delete(key); collection.delete(document.uri);
    }),
    vscode.workspace.onDidChangeConfiguration(event => { if (event.affectsConfiguration('jsonlintPlus.pythonPath')) vscode.workspace.textDocuments.forEach(schedule); }),
    { dispose() { for (const timer of timers.values()) clearTimeout(timer); for (const child of processes.values()) child.kill(); } });
  vscode.workspace.textDocuments.forEach(schedule);
}
module.exports = { activate };
