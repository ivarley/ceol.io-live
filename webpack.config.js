const path = require('path');

module.exports = {
  entry: {
    'stateManager': './src/ts/components/stateManager.ts',
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
    library: {
      type: 'var',
      name: '[name]', // This makes StateManager available as global StateManager
    },
  },
  devtool: 'source-map',
};