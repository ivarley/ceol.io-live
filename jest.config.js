module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/src/ts', '<rootDir>/tests/js'],
  testMatch: [
    '**/__tests__/**/*.test.ts',
    '**/?(*.)+(spec|test).ts'
  ],
  transform: {
    '^.+\\.ts$': 'ts-jest',
  },
  globals: {
    'ts-jest': {
      tsconfig: {
        strict: false,
        noUncheckedIndexedAccess: false
      }
    }
  },
  collectCoverageFrom: [
    'src/ts/**/*.ts',
    '!src/ts/**/*.d.ts',
  ],
  coverageDirectory: 'coverage/js',
  coverageReporters: ['text', 'lcov', 'html'],
  setupFilesAfterEnv: ['<rootDir>/tests/js/setup.ts'],
  moduleFileExtensions: ['ts', 'js'],
  verbose: true,
};