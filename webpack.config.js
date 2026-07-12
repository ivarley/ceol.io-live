const path = require('path');

module.exports = {
  entry: {
    // NOT pill-logger code (spec 035 §1f): emitted to static/js/shared/ so that
    // static/js/dist/ holds only the pill editor and can be deleted wholesale.
    'shared/attendance': './src/ts/attendance.ts',
    // modalManager's only remaining consumer IS now the pill logger
    // (session_instance_detail.html) — it dies with it in spec 035 Step 6, but
    // keeps its shared/ output path so the quarantined template stays untouched.
    'shared/modalManager': './src/ts/components/modalManager.ts',
    // Pill-logger modules — die with templates/session_instance_detail.html.
    'dist/stateManager': './src/ts/components/stateManager.ts',
    'dist/undoRedoManager': './src/ts/components/undoRedoManager.ts',
    'dist/keyboardHandler': './src/ts/components/keyboardHandler.ts',
    'dist/pillInteraction': './src/ts/components/pillInteraction.ts',
    'dist/clipboardManager': './src/ts/components/clipboardManager.ts',
    'dist/contextMenu': './src/ts/components/contextMenu.ts',
    'dist/autoSave': './src/ts/components/autoSave.ts',
    'dist/pillRenderer': './src/ts/components/pillRenderer.ts',
    'dist/pillSelection': './src/ts/components/pillSelection.ts',
    'dist/cursorManager': './src/ts/components/cursorManager.ts',
    'dist/dragDrop': './src/ts/components/dragDrop.ts',
    'dist/textInput': './src/ts/components/textInput.ts',
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: {
          loader: 'ts-loader',
          options: {
            configFile: 'tsconfig.json',
            transpileOnly: true,
          }
        },
        exclude: /node_modules/,
      },
    ],
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
  },
  output: {
    filename: '[name].js',
    path: path.resolve(__dirname, 'static/js'),
    // Remove library config since we're manually setting window globals in TS
  },
  devtool: 'source-map',
};