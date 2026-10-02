// Read-only compiler oracle. No project code is executed and no output is emitted.
const fs = require('node:fs');
const path = require('node:path');
const ts = require(process.argv[2]);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const configFile = ts.readConfigFile(path.join(input.root, 'tsconfig.json'), ts.sys.readFile);
const parsed = ts.parseJsonConfigFileContent(configFile.config, ts.sys, input.root);
const program = ts.createProgram(parsed.fileNames, parsed.options);
const checker = program.getTypeChecker();
const relative = name => path.relative(input.root, name).split(path.sep).join('/');
const requestedImports = [...(input.imports || [])];
for (const file of input.scan || []) {
  const full = path.join(input.root, file);
  const source = ts.createSourceFile(full, ts.sys.readFile(full), ts.ScriptTarget.Latest, true);
  function visit(node) {
    let specifier;
    let kind;
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
      specifier = node.moduleSpecifier;
      kind = 'static';
    } else if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) {
      specifier = node.moduleReference.expression;
      kind = 'require';
    } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      specifier = node.arguments[0];
      kind = 'dynamic';
    }
    if (specifier && ts.isStringLiteralLike(specifier)) {
      requestedImports.push({importer: file, specifier: specifier.text, kind});
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
}
const imports = requestedImports.map(item => {
  const resolved = ts.resolveModuleName(item.specifier, path.join(input.root, item.importer),
    parsed.options, ts.sys).resolvedModule;
  return {...item, resolved: resolved ? relative(resolved.resolvedFileName) : null};
});
const publicExports = {};
for (const name of input.exports || []) {
  const source = program.getSourceFile(path.join(input.root, name));
  const symbol = source && checker.getSymbolAtLocation(source);
  publicExports[name] = symbol ? checker.getExportsOfModule(symbol).map(s => ({
    name: s.name,
    flags: (s.flags & ts.SymbolFlags.Alias) ? checker.getAliasedSymbol(s).flags : s.flags,
  })) : [];
}
const diagnostics = [...parsed.errors, ...ts.getPreEmitDiagnostics(program)].map(d => ({
  code: d.code, file: d.file ? relative(d.file.fileName) : null,
  message: ts.flattenDiagnosticMessageText(d.messageText, '\n'),
}));
console.log(JSON.stringify({version: ts.version, imports, exports: publicExports, diagnostics,
  inputs: parsed.fileNames.map(relative),
  sources: program.getSourceFiles().filter(f => !f.isDeclarationFile).map(f => relative(f.fileName)),
  commonSourceDirectory: relative(program.getCommonSourceDirectory()),
}));
