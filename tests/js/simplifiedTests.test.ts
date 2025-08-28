import { StateManager } from '../../src/ts/components/stateManager';

describe('Core TypeScript Components Integration', () => {
    test('StateManager should be importable and have basic functionality', () => {
        expect(StateManager).toBeDefined();
        expect(typeof StateManager.initialize).toBe('function');
        expect(typeof StateManager.getTunePillsData).toBe('function');
        expect(typeof StateManager.generateId).toBe('function');
    });
    
    test('StateManager should maintain state correctly', () => {
        const mockCallback = jest.fn();
        StateManager.initialize(mockCallback);
        
        expect(StateManager.getTunePillsData()).toEqual([]);
        expect(StateManager.canUndo()).toBe(false);
        expect(StateManager.canRedo()).toBe(false);
    });
    
    test('StateManager should generate unique IDs', () => {
        const id1 = StateManager.generateId();
        const id2 = StateManager.generateId();
        
        expect(id1).toMatch(/^pill_[a-z0-9]+$/);
        expect(id2).toMatch(/^pill_[a-z0-9]+$/);
        expect(id1).not.toBe(id2);
    });
});