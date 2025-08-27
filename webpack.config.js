const path = require('path');

module.exports = {
  entry: {
    'stateManager': './src/ts/components/stateManager.ts',
    'undoRedoManager': './src/ts/components/undoRedoManager.ts',
    // Add other modules as we convert them
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