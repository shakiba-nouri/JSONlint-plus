const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');

function activate(context) {
  const collection = vscode.languages.createDiagnosticCollection('JSONLint+');
  const output = vscode.window.createOutputChannel('JSONLint+');
  const timers = new Map();
  const processes = new Map();
  const results = new Map();
  let lastSchemaError = '';
  let reportedFailure = false;
  context.subscriptions.push(collection, output);

  function schedule(document) {
    const key = document.uri.toString();
    clearTimeout(timers.get(key));
    const running = processes.get(key);
    if (running) { processes.delete(key); running.kill(); }
    if (document.languageId !== 'json') { collection.delete(document.uri); return; }
    timers.set(key, setTimeout(() => { timers.delete(key); validate(document); }, 250));
  }
  async function validate(document) {
    const key = document.uri.toString();
    const version = document.version;
    const source = document.getText();
    const config = vscode.workspace.getConfiguration('jsonlintPlus', document.uri);
    const python = config.get('pythonPath');
    const schemaPath = config.get('schemaPath');
    const request = { text: source };
    if (schemaPath) {
      try {
        const folder = vscode.workspace.getWorkspaceFolder(document.uri);
        if (!path.isAbsolute(schemaPath) && !folder) throw new Error('A relative schema path requires an open workspace folder.');
        const resolved = path.isAbsolute(schemaPath) ? schemaPath : path.join(folder.uri.fsPath, schemaPath);
        request.schema = JSON.parse(Buffer.from(await vscode.workspace.fs.readFile(vscode.Uri.file(resolved))).toString('utf8').replace(/^\uFEFF/, ''));
      } catch (err) {
        collection.delete(document.uri);
        results.delete(key);
        const message = `JSONLint+ schema error: ${err.message}`;
        output.appendLine(message);
        if (lastSchemaError !== message) { lastSchemaError = message; vscode.window.showErrorMessage(message); }
        return;
      }
    }
    if (document.isClosed || document.version !== version) return;
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
        results.set(key, { version, result });
        if (result.schemaError) {
          output.appendLine(result.schemaError);
          if (lastSchemaError !== result.schemaError) { lastSchemaError = result.schemaError; vscode.window.showErrorMessage(result.schemaError); }
        } else { lastSchemaError = ''; }
        const diagnostics = result.diagnostics.map(item => {
          const line = Math.max(0, Math.min(item.line - 1, document.lineCount - 1));
          const lineText = document.lineAt(line).text;
          const character = Array.from(lineText).slice(0, item.column - 1).join('').length;
          const start = new vscode.Position(line, character);
          const end = new vscode.Position(line, Math.min(character + 1, lineText.length));
          const diagnostic = new vscode.Diagnostic(new vscode.Range(start, end), item.message, vscode.DiagnosticSeverity.Error);
          diagnostic.source = 'JSONLint+';
          return diagnostic;
        });
        reportedFailure = false;
        collection.set(document.uri, diagnostics);
      } catch (err) { collection.delete(document.uri); output.appendLine(String(err)); vscode.window.showErrorMessage('JSONLint+ returned an invalid response. See the output channel.'); }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify(request));
  }
  function showAnalysis(kind) {
    const document = vscode.window.activeTextEditor?.document;
    if (!document || document.languageId !== 'json') { vscode.window.showInformationMessage('Open a JSON file first.'); return; }
    const cached = results.get(document.uri.toString());
    if (!cached || cached.version !== document.version) { vscode.window.showInformationMessage('Analysis is pending. Try again shortly.'); return; }
    const value = cached.result[kind];
    if (!value) { vscode.window.showInformationMessage('Fix the syntax errors to inspect the ' + kind.toUpperCase() + '.'); return; }
    const text = JSON.stringify(value, null, 2);
    vscode.workspace.openTextDocument({ language: 'json', content: text }).then(doc => vscode.window.showTextDocument(doc, { preview: true, viewColumn: vscode.ViewColumn.Beside }));
  }
  context.subscriptions.push(vscode.commands.registerCommand('jsonlintPlus.showTokens', () => showAnalysis('tokens')),
    vscode.commands.registerCommand('jsonlintPlus.showAst', () => showAnalysis('ast')));
  context.subscriptions.push(vscode.languages.registerDocumentFormattingEditProvider({ language: 'json' }, {
    provideDocumentFormattingEdits(document, options, cancellation) {
      const version = document.version;
      const source = document.getText();
      const python = vscode.workspace.getConfiguration('jsonlintPlus', document.uri).get('pythonPath');
      const indent = options.insertSpaces ? ' '.repeat(Math.max(1, Math.min(options.tabSize || 2, 16))) : '\t';
      const eol = document.eol === vscode.EndOfLine.CRLF ? '\r\n' : '\n';
      return new Promise(resolve => {
        const child = spawn(python, ['-m', 'jsonlint_plus.vscode_bridge'], {
          cwd: context.extensionPath,
          env: { ...process.env, PYTHONPATH: path.join(context.extensionPath, 'src') },
          windowsHide: true
        });
        let stdout = '', stderr = '', done = false;
        const finish = value => { if (!done) { done = true; subscription.dispose(); resolve(value); } };
        const subscription = cancellation.onCancellationRequested(() => { child.kill(); finish([]); });
        child.stdout.setEncoding('utf8'); child.stdout.on('data', data => stdout += data);
        child.stderr.setEncoding('utf8'); child.stderr.on('data', data => stderr += data);
        child.on('error', err => { output.appendLine(err.message); vscode.window.showErrorMessage('JSONLint+ formatting could not start Python.'); finish([]); });
        child.on('close', code => {
          if (done || cancellation.isCancellationRequested || document.isClosed || document.version !== version) { finish([]); return; }
          if (code !== 0) { output.appendLine(stderr); vscode.window.showErrorMessage('JSONLint+ formatting failed. See the JSONLint+ output channel.'); finish([]); return; }
          try {
            const result = JSON.parse(stdout);
            if (result.error) { vscode.window.showInformationMessage('JSONLint+: Fix syntax errors before formatting.'); finish([]); return; }
            finish([vscode.TextEdit.replace(new vscode.Range(document.positionAt(0), document.positionAt(source.length)), result.text)]);
          } catch (err) { output.appendLine(String(err)); vscode.window.showErrorMessage('JSONLint+ returned an invalid formatting response.'); finish([]); }
        });
        child.stdin.on('error', () => {});
        child.stdin.end(JSON.stringify({action: 'format', text: source, indent, eol}));
      });
    }
  }));
  context.subscriptions.push(vscode.languages.registerCodeActionsProvider({ language: 'json' }, {
    provideCodeActions(document, range, context) {
      // VS Code may recreate Diagnostic objects before invoking this provider,
      // so custom properties attached to a Diagnostic cannot carry the edit.
      const cached = results.get(document.uri.toString());
      if (!cached || cached.version !== document.version) return [];
      const chars = Array.from(document.getText());
      const actions = [];
      for (const diagnostic of context.diagnostics) {
        if (diagnostic.source !== 'JSONLint+') continue;
        const item = cached.result.diagnostics.find(entry => {
          if (!entry.fix || entry.message !== diagnostic.message || entry.line - 1 !== diagnostic.range.start.line) return false;
          const lineText = document.lineAt(entry.line - 1).text;
          return Array.from(lineText).slice(0, entry.column - 1).join('').length === diagnostic.range.start.character;
        });
        if (!item) continue;
        const fix = item.fix;
        // Python offsets count Unicode code points; VS Code counts UTF-16 units.
        const start = chars.slice(0, fix.start).join('').length;
        const end = chars.slice(0, fix.end).join('').length;
        const action = new vscode.CodeAction('JSONLint+: ' + fix.title, vscode.CodeActionKind.QuickFix);
        action.edit = new vscode.WorkspaceEdit();
        action.edit.replace(document.uri, new vscode.Range(document.positionAt(start), document.positionAt(end)), fix.text);
        action.diagnostics = [diagnostic]; action.isPreferred = true;
        actions.push(action);
      }
      return actions;
    }
  }, { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }));
  context.subscriptions.push(vscode.workspace.onDidOpenTextDocument(schedule),
    vscode.workspace.onDidChangeTextDocument(event => schedule(event.document)),
    vscode.workspace.onDidCloseTextDocument(document => {
      const key = document.uri.toString(); clearTimeout(timers.get(key)); timers.delete(key); results.delete(key);
      const child = processes.get(key); if (child) child.kill(); processes.delete(key); collection.delete(document.uri);
    }),
    vscode.workspace.onDidChangeConfiguration(event => { if (event.affectsConfiguration('jsonlintPlus')) vscode.workspace.textDocuments.forEach(schedule); }),
    { dispose() { for (const timer of timers.values()) clearTimeout(timer); for (const child of processes.values()) child.kill(); } });
  vscode.workspace.textDocuments.forEach(schedule);
}
module.exports = { activate };
