// Mock DOM environment for testing
global.beforeEach = beforeEach;
global.afterEach = afterEach;

// Mock fetch if needed
global.fetch = jest.fn();

// Clean up after each test
afterEach(() => {
  jest.clearAllMocks();
  // Clean up DOM
  document.body.innerHTML = '';
  document.head.innerHTML = '';
});