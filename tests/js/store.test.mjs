/**
 * Shopping-list state tests.
 *
 * These exist because two bugs reached production that Python tests could not
 * structurally catch: the parser was right both times and the browser state
 * layer was wrong. `store.js` is pure logic with no DOM dependency, so it is
 * worth testing directly.
 *
 * Run with:  node --test tests/js/
 * No dependencies and no build step - Node's built-in test runner only.
 */

import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';

/** Minimal localStorage, so store.js can run outside a browser. */
class MemoryStorage {
  #data = new Map();
  getItem(key) {
    return this.#data.has(key) ? this.#data.get(key) : null;
  }
  setItem(key, value) {
    this.#data.set(key, String(value));
  }
  removeItem(key) {
    this.#data.delete(key);
  }
  clear() {
    this.#data.clear();
  }
}

globalThis.window = {
  localStorage: new MemoryStorage(),
  crypto: { randomUUID: () => `id-${Math.random().toString(36).slice(2)}` },
};

const { store } = await import('../../web/js/store.js');

/** Start each test from a known, empty list. */
function reset(items = []) {
  window.localStorage.clear();
  store.items = items.map((item, index) => ({
    id: `test-${index}`,
    name: item.name,
    quantity: item.quantity ?? 1,
    unit: item.unit ?? null,
    category: item.category ?? 'Other',
    completed: false,
    addedAt: new Date().toISOString(),
  }));
  store.history = [];
  store.undoSnapshot = null;
}

const find = (name) => store.items.find((item) => item.name === name);

describe('removing a quantity', () => {
  beforeEach(() => {
    reset([
      { name: 'eggs', quantity: 9 },
      { name: 'milk', quantity: 3, unit: 'litre' },
    ]);
  });

  it('decrements rather than deleting the whole entry', () => {
    // Regression: "remove 7 eggs" deleted all nine.
    const result = store.remove('eggs', 7);

    assert.equal(result.removedAll, false);
    assert.equal(result.removed, 7);
    assert.equal(result.remaining, 2);
    assert.equal(find('eggs').quantity, 2);
  });

  it('keeps the unit when decrementing', () => {
    const result = store.remove('milk', 1);

    assert.equal(result.removedAll, false);
    assert.equal(result.remaining, 2);
    assert.equal(find('milk').unit, 'litre');
  });

  it('deletes the entry when no quantity is given', () => {
    const result = store.remove('eggs');

    assert.equal(result.removedAll, true);
    assert.equal(find('eggs'), undefined);
  });

  it('deletes the entry when the quantity covers everything listed', () => {
    assert.equal(store.remove('eggs', 9).removedAll, true);
    assert.equal(find('eggs'), undefined);
  });

  it('deletes the entry when asked for more than is listed', () => {
    assert.equal(store.remove('milk', 99).removedAll, true);
    assert.equal(find('milk'), undefined);
  });

  it('returns null for an item that is not on the list', () => {
    assert.equal(store.remove('helicopter', 2), null);
  });

  it('ignores a nonsensical quantity and deletes', () => {
    for (const quantity of [0, -3, Number.NaN, 'seven']) {
      reset([{ name: 'eggs', quantity: 9 }]);
      assert.equal(store.remove('eggs', quantity).removedAll, true);
    }
  });

  it('can be undone', () => {
    store.remove('eggs', 7);
    assert.equal(find('eggs').quantity, 2);

    assert.equal(store.undo(), true);
    assert.equal(find('eggs').quantity, 9);
  });
});

describe('adding', () => {
  beforeEach(() => reset([{ name: 'milk', quantity: 2, unit: 'litre' }]));

  it('merges an exact name match and sums the quantity', () => {
    const result = store.add({ name: 'milk', quantity: 3, unit: 'litre' });

    assert.equal(result.merged, true);
    assert.equal(find('milk').quantity, 5);
    assert.equal(store.items.length, 1);
  });

  it('keeps a related product separate', () => {
    // Regression: "add almond milk" merged into the plain "milk" entry.
    store.add({ name: 'almond milk', quantity: 1 });

    assert.equal(store.items.length, 2);
    assert.equal(find('milk').quantity, 2);
    assert.equal(find('almond milk').quantity, 1);
  });

  it('defaults a missing quantity to one', () => {
    store.add({ name: 'bread' });
    assert.equal(find('bread').quantity, 1);
  });

  it('records the addition in history for the recommender', () => {
    store.add({ name: 'bread' });
    assert.ok(store.history.some((entry) => entry.name === 'bread'));
  });
});

describe('finding an item by a spoken name', () => {
  beforeEach(() =>
    reset([{ name: 'almond milk' }, { name: 'milk' }, { name: 'whole wheat bread' }])
  );

  it('prefers an exact match over a longer name containing it', () => {
    // "milk" must find "milk", not whichever entry happens to be first.
    assert.equal(store.find('milk').name, 'milk');
  });

  it('falls back to a whole-word match', () => {
    assert.equal(store.find('wheat').name, 'whole wheat bread');
  });

  it('is case insensitive', () => {
    assert.equal(store.find('MILK').name, 'milk');
  });

  it('returns null for an unknown name', () => {
    assert.equal(store.find('helicopter'), null);
  });
});

describe('quantity controls', () => {
  beforeEach(() => reset([{ name: 'eggs', quantity: 3 }]));

  it('removes the item when decremented to zero', () => {
    const id = find('eggs').id;
    store.setQuantity(id, 0);
    assert.equal(find('eggs'), undefined);
  });

  it('updates the quantity otherwise', () => {
    store.setQuantity(find('eggs').id, 8);
    assert.equal(find('eggs').quantity, 8);
  });
});

describe('storage failures', () => {
  it('keeps working in memory when localStorage throws', () => {
    reset([]);

    // Swap in the failing storage only after the fixture is set up, so the
    // test exercises store.js rather than the harness.
    const original = window.localStorage;
    window.localStorage = {
      getItem() {
        throw new Error('blocked');
      },
      setItem() {
        throw new Error('quota exceeded');
      },
      removeItem() {},
      clear() {
        throw new Error('blocked');
      },
    };

    try {
      store.add({ name: 'milk', quantity: 1 });
      // The write failed, but the item is still usable for this session.
      assert.equal(store.items.length, 1);
      assert.equal(store.storageAvailable, false);
    } finally {
      window.localStorage = original;
    }
  });
});
