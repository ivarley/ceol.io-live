const path = require('path');

module.exports = {
  entry: {
    'stateManager': './src/ts/components/stateManager.ts',
    'undoRedoManager': './src/ts/components/undoRedoManager.ts',
    'keyboardHandler': './src/ts/components/keyboardHandler.ts',
    'pillInteraction': './src/ts/components/pillInteraction.ts',
    'clipboardManager': './src/ts/components/clipboardManager.ts',
    'modalManager': './src/ts/components/modalManager.ts',
    'contextMenu': './src/ts/components/contextMenu.ts',
    'autoSave': './src/ts/components/autoSave.ts',
    'pillRenderer': './src/ts/components/pillRenderer.ts',
    'pillSelection': './src/ts/components/pillSelection.ts',
    'cursorManager': './src/ts/components/cursorManager.ts',
    'dragDrop': './src/ts/components/dragDrop.ts',
    'textInput': './src/ts/components/textInput.ts',
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
    path: path.resolve(__dirname, 'static/js/dist'),
    // Remove library config since we're manually setting window globals in TS
  },
  devtool: 'source-map',
};