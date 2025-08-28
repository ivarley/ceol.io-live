import { StateManager, TunePill, TuneSet, TunePillsData, RawTuneSets } from '../../src/ts/components/stateManager';

describe('StateManager', () => {
    let mockCallback: jest.Mock;

    beforeEach(() => {
        mockCallback = jest.fn();
        StateManager.initialize(mockCallback);
    });

    afterEach(() => {
        StateManager.clearHistory();
    });

    describe('initialization', () => {
        test('should initialize with empty data and clear history', () => {
            expect(StateManager.getTunePillsData()).toEqual([]);
            expect(StateManager.getUndoStackSize()).toBe(0);
            expect(StateManager.getRedoStackSize()).toBe(0);
            expect(StateManager.canUndo()).toBe(false);
            expect(StateManager.canRedo()).toBe(false);
        });
    });

    describe('basic data management', () => {
        test('should set and get tune pills data', () => {
            const testData: TunePillsData = [[{
                id: 'test1',
                orderNumber: 1,
                tuneId: 123,
                tuneName: 'Test Tune',
                setting: 'A major',
                tuneType: 'jig',
                state: 'linked'
            }]];

            StateManager.setTunePillsData(testData);
            
            expect(StateManager.getTunePillsData()).toEqual(testData);
            expect(mockCallback).toHaveBeenCalledTimes(1);
        });

        test('should generate unique IDs', () => {
            const id1 = StateManager.generateId();
            const id2 = StateManager.generateId();
            
            expect(id1).toMatch(/^pill_[a-z0-9]+$/);
            expect(id2).toMatch(/^pill_[a-z0-9]+$/);
            expect(id1).not.toBe(id2);
        });
    });

    describe('undo/redo functionality', () => {
        let sampleTune: TunePill;

        beforeEach(() => {
            sampleTune = {
                id: 'test1',
                orderNumber: 1,
                tuneId: 123,
                tuneName: 'Test Tune',
                setting: 'A major',
                tuneType: 'jig',
                state: 'linked'
            };
        });

        test('should save to undo and allow undo/redo', () => {
            const initialData: TunePillsData = [[sampleTune]];
            StateManager.setTunePillsData(initialData);
            StateManager.saveToUndo();

            const modifiedTune = { ...sampleTune, tuneName: 'Modified Tune' };
            const modifiedData: TunePillsData = [[modifiedTune]];
            StateManager.setTunePillsData(modifiedData);

            expect(StateManager.canUndo()).toBe(true);
            expect(StateManager.getUndoStackSize()).toBe(1);

            // Undo
            const undoSuccess = StateManager.undo();
            expect(undoSuccess).toBe(true);
            expect(StateManager.getTunePillsData()).toEqual(initialData);
            expect(mockCallback).toHaveBeenCalled();

            // Redo
            expect(StateManager.canRedo()).toBe(true);
            const redoSuccess = StateManager.redo();
            expect(redoSuccess).toBe(true);
            expect(StateManager.getTunePillsData()).toEqual(modifiedData);
        });

        test('should clear redo stack when new action is performed', () => {
            StateManager.setTunePillsData([[sampleTune]]);
            StateManager.saveToUndo();
            
            StateManager.setTunePillsData([[{ ...sampleTune, tuneName: 'Modified' }]]);
            StateManager.undo();
            
            expect(StateManager.canRedo()).toBe(true);
            
            // New action should clear redo stack
            StateManager.saveToUndo();
            StateManager.setTunePillsData([[{ ...sampleTune, tuneName: 'New Action' }]]);
            
            expect(StateManager.canRedo()).toBe(false);
        });

        test('should limit undo stack size', () => {
            // Add more than maxUndoSize (50) items
            for (let i = 0; i < 55; i++) {
                StateManager.setTunePillsData([[{ ...sampleTune, orderNumber: i }]]);
                StateManager.saveToUndo();
            }

            expect(StateManager.getUndoStackSize()).toBe(50);
        });

        test('should return false when trying to undo/redo empty stacks', () => {
            expect(StateManager.undo()).toBe(false);
            expect(StateManager.redo()).toBe(false);
        });
    });

    describe('tune set operations', () => {
        let sampleTune: TunePill;
        let sampleSet: TuneSet;

        beforeEach(() => {
            sampleTune = {
                id: 'test1',
                orderNumber: 1,
                tuneId: 123,
                tuneName: 'Test Tune',
                setting: 'A major',
                tuneType: 'jig',
                state: 'linked'
            };
            sampleSet = [sampleTune];
        });

        test('should add tune set', () => {
            StateManager.addTuneSet(sampleSet);
            
            expect(StateManager.getTunePillsData()).toEqual([sampleSet]);
            expect(StateManager.getSetCount()).toBe(1);
            expect(mockCallback).toHaveBeenCalled();
        });

        test('should remove tune set', () => {
            StateManager.setTunePillsData([sampleSet, [{ ...sampleTune, id: 'test2' }]]);
            
            StateManager.removeTuneSet(0);
            
            expect(StateManager.getSetCount()).toBe(1);
            expect(StateManager.getTunePillsData()[0][0].id).toBe('test2');
        });

        test('should not remove tune set with invalid index', () => {
            StateManager.setTunePillsData([sampleSet]);
            
            StateManager.removeTuneSet(5);
            StateManager.removeTuneSet(-1);
            
            expect(StateManager.getSetCount()).toBe(1);
        });
    });

    describe('individual tune operations', () => {
        let sampleTune: TunePill;

        beforeEach(() => {
            sampleTune = {
                id: 'test1',
                orderNumber: 1,
                tuneId: 123,
                tuneName: 'Test Tune',
                setting: 'A major',
                tuneType: 'jig',
                state: 'linked'
            };
            StateManager.setTunePillsData([[sampleTune]]);
        });

        test('should add tune to existing set', () => {
            const newTune: TunePill = { ...sampleTune, id: 'test2', tuneName: 'New Tune' };
            
            StateManager.addTune(0, newTune);
            
            expect(StateManager.getTunePillsData()[0].length).toBe(2);
            expect(StateManager.getTunePillsData()[0][1]).toEqual(newTune);
        });

        test('should add tune at specific index', () => {
            const existingSet = [sampleTune, { ...sampleTune, id: 'test2' }];
            StateManager.setTunePillsData([existingSet]);
            
            const newTune: TunePill = { ...sampleTune, id: 'test3', tuneName: 'Inserted Tune' };
            StateManager.addTune(0, newTune, 1);
            
            expect(StateManager.getTunePillsData()[0].length).toBe(3);
            expect(StateManager.getTunePillsData()[0][1]).toEqual(newTune);
        });

        test('should remove tune', () => {
            const twoTunes = [sampleTune, { ...sampleTune, id: 'test2' }];
            StateManager.setTunePillsData([twoTunes]);
            
            StateManager.removeTune(0, 0);
            
            expect(StateManager.getTunePillsData()[0].length).toBe(1);
            expect(StateManager.getTunePillsData()[0][0].id).toBe('test2');
        });

        test('should remove empty set when removing last tune', () => {
            StateManager.removeTune(0, 0);
            
            expect(StateManager.getSetCount()).toBe(0);
        });

        test('should update tune', () => {
            StateManager.updateTune(0, 0, { tuneName: 'Updated Tune', setting: 'D major' });
            
            const updatedTune = StateManager.getTunePillsData()[0][0];
            expect(updatedTune.tuneName).toBe('Updated Tune');
            expect(updatedTune.setting).toBe('D major');
            expect(updatedTune.id).toBe(sampleTune.id); // Should preserve other properties
        });

        test('should not operate on invalid indices', () => {
            StateManager.addTune(5, sampleTune);
            StateManager.removeTune(5, 0);
            StateManager.removeTune(0, 5);
            StateManager.updateTune(5, 0, { tuneName: 'Should not work' });
            StateManager.updateTune(0, 5, { tuneName: 'Should not work' });
            
            // Data should remain unchanged
            expect(StateManager.getTunePillsData()).toEqual([[sampleTune]]);
        });
    });

    describe('data conversion', () => {
        test('should convert raw tune sets to pills', () => {
            const rawTuneSets: RawTuneSets = [
                [[1, false, 123, 'Test Tune 1', 'A major', 'jig']],
                [[2, false, null, 'Unlinked Tune', 'D major', 'reel']]
            ];

            StateManager.convertTuneSetsToPills(rawTuneSets);

            const result = StateManager.getTunePillsData();
            expect(result).toHaveLength(2);
            expect(result[0]).toHaveLength(1);
            expect(result[1]).toHaveLength(1);
            
            expect(result[0][0].tuneName).toBe('Test Tune 1');
            expect(result[0][0].state).toBe('linked');
            expect(result[1][0].tuneName).toBe('Unlinked Tune');
            expect(result[1][0].state).toBe('unlinked');
        });

        test('should handle empty raw tune sets', () => {
            StateManager.convertTuneSetsToPills([]);
            expect(StateManager.getTunePillsData()).toEqual([]);
            
            StateManager.convertTuneSetsToPills(null as any);
            expect(StateManager.getTunePillsData()).toEqual([]);
        });

        test('should skip callback when requested', () => {
            const rawTuneSets: RawTuneSets = [[[1, false, 123, 'Test', 'A', 'jig']]];
            
            StateManager.convertTuneSetsToPills(rawTuneSets, true);
            
            expect(mockCallback).not.toHaveBeenCalled();
        });
    });

    describe('search and utility functions', () => {
        beforeEach(() => {
            const testData: TunePillsData = [
                [
                    { id: 'tune1', orderNumber: 1, tuneId: 123, tuneName: 'First', setting: 'A', tuneType: 'jig', state: 'linked' },
                    { id: 'tune2', orderNumber: 2, tuneId: 456, tuneName: 'Second', setting: 'D', tuneType: 'reel', state: 'linked' }
                ],
                [
                    { id: 'tune3', orderNumber: 3, tuneId: null, tuneName: 'Third', setting: 'G', tuneType: 'hornpipe', state: 'unlinked' }
                ]
            ];
            StateManager.setTunePillsData(testData);
        });

        test('should find tune by ID', () => {
            const position = StateManager.findTuneById('tune2');
            
            expect(position).not.toBeNull();
            expect(position!.setIndex).toBe(0);
            expect(position!.tuneIndex).toBe(1);
            expect(position!.tune.tuneName).toBe('Second');
        });

        test('should return null for non-existent tune ID', () => {
            const position = StateManager.findTuneById('nonexistent');
            expect(position).toBeNull();
        });

        test('should count tunes correctly', () => {
            expect(StateManager.getTuneCount()).toBe(3);
        });

        test('should count sets correctly', () => {
            expect(StateManager.getSetCount()).toBe(2);
        });
    });

    describe('data import/export', () => {
        let testData: TunePillsData;

        beforeEach(() => {
            testData = [[{
                id: 'test1',
                orderNumber: 1,
                tuneId: 123,
                tuneName: 'Export Test',
                setting: 'A major',
                tuneType: 'jig',
                state: 'linked'
            }]];
            StateManager.setTunePillsData(testData);
        });

        test('should export data as deep copy', () => {
            const exported = StateManager.exportData();
            
            expect(exported).toEqual(testData);
            expect(exported).not.toBe(testData); // Should be different object references
            expect(exported[0]).not.toBe(testData[0]);
        });

        test('should import data and trigger callback', () => {
            const importData: TunePillsData = [[{
                id: 'imported1',
                orderNumber: 1,
                tuneId: 789,
                tuneName: 'Imported Tune',
                setting: 'D major',
                tuneType: 'reel',
                state: 'linked'
            }]];

            StateManager.importData(importData);

            expect(StateManager.getTunePillsData()).toEqual(importData);
            expect(StateManager.canUndo()).toBe(true); // Should save to undo before import
            expect(mockCallback).toHaveBeenCalled();
        });
    });
});