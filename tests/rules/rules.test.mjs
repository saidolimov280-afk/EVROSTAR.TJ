// Firestore security rules tests (run in CI against the Firestore emulator).
// The rules file has PASTE_ADMIN_UID as a placeholder; the test swaps in a known admin uid.
import { readFileSync } from 'node:fs';
import { test, before, after, beforeEach } from 'node:test';
import { initializeTestEnvironment, assertSucceeds, assertFails } from '@firebase/rules-unit-testing';
import { doc, getDoc, setDoc, updateDoc, deleteDoc, collection, getDocs, query, where } from 'firebase/firestore';

const rules = readFileSync(new URL('../../firestore.rules', import.meta.url), 'utf8').replace(/request\.auth\.uid in \[[^\]]*\]/, "request.auth.uid in ['admin1']");
let env;
before(async () => {
  env = await initializeTestEnvironment({ projectId: 'demo-evrostar', firestore: { rules, host: '127.0.0.1', port: 8080 } });
});
after(async () => { await env.cleanup(); });
beforeEach(async () => {
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async ctx => {
    const db = ctx.firestore();
    await setDoc(doc(db, 'products/p1'), { name: 'Panel', price: 950 });
    await setDoc(doc(db, 'orders/o1'), { status: 'new', name: 'X' });
    await setDoc(doc(db, 'orders/mine'), { status: 'done', name: 'Ali', uid: 'c1' });
    await setDoc(doc(db, 'orderStatus/o1'), { status: 'new' });
    await setDoc(doc(db, 'reviews/r1'), { status: 'approved', rating: 5 });
    await setDoc(doc(db, 'reviews/r2'), { status: 'pending', rating: 4 });
    await setDoc(doc(db, 'customers/c1'), { name: 'Ali', phone: '+992900000001', code: 'EVRO-AAAAAA' });
  });
});

const guest = () => env.unauthenticatedContext().firestore();
const admin = () => env.authenticatedContext('admin1', { email: 'admin@example.com', firebase: { sign_in_provider: 'password' } }).firestore();
const customer = (uid = 'c1', phone = '+992900000001') =>
  env.authenticatedContext(uid, { phone_number: phone, firebase: { sign_in_provider: 'phone' } }).firestore();
const profile = (phone = '+992900000001') => ({ name: 'Ali', city: 'Hisor', phone, code: 'EVRO-AAAAAA', lang: 'tg' });

test('catalog is public to read, admin-only to change', async () => {
  await assertSucceeds(getDoc(doc(guest(), 'products/p1')));
  await assertFails(setDoc(doc(guest(), 'products/p2'), { name: 'x' }));
  await assertFails(updateDoc(doc(customer(), 'products/p1'), { price: 1 }));
  await assertSucceeds(updateDoc(doc(admin(), 'products/p1'), { price: 900 }));
});

test('signed-in customer cannot read or change orders (the key risk)', async () => {
  await assertFails(getDoc(doc(customer(), 'orders/o1')));
  await assertFails(getDocs(collection(customer(), 'orders')));
  await assertFails(updateDoc(doc(customer(), 'orders/o1'), { status: 'done' }));
  await assertSucceeds(getDocs(collection(admin(), 'orders')));
});

test('anyone can place an order and look up its status by id', async () => {
  await assertSucceeds(setDoc(doc(guest(), 'orders/o2'), { status: 'new', name: 'Y' }));
  await assertFails(setDoc(doc(guest(), 'orders/o3'), { status: 'done' }));
  await assertSucceeds(setDoc(doc(guest(), 'orderStatus/o2'), { status: 'new' }));
  await assertSucceeds(getDoc(doc(guest(), 'orderStatus/o1')));
  await assertFails(getDocs(collection(guest(), 'orderStatus')));
  await assertFails(updateDoc(doc(guest(), 'orderStatus/o1'), { status: 'done' }));
  await assertSucceeds(setDoc(doc(admin(), 'orderStatus/o1'), { status: 'done' }, { merge: true }));
});

test('reviews: public sees approved only, new ones are pending', async () => {
  await assertSucceeds(getDocs(query(collection(guest(), 'reviews'), where('status', '==', 'approved'))));
  await assertFails(getDoc(doc(guest(), 'reviews/r2')));
  await assertSucceeds(setDoc(doc(guest(), 'reviews/r3'), { status: 'pending', rating: 5 }));
  await assertFails(setDoc(doc(guest(), 'reviews/r4'), { status: 'approved', rating: 5 }));
  await assertSucceeds(updateDoc(doc(admin(), 'reviews/r2'), { status: 'approved' }));
});

test('stock alerts: create waiting, admin reads', async () => {
  await assertSucceeds(setDoc(doc(guest(), 'stockAlerts/a1'), { status: 'waiting', phone: '900' }));
  await assertFails(getDocs(collection(customer(), 'stockAlerts')));
  await assertSucceeds(getDocs(collection(admin(), 'stockAlerts')));
});

test('customers: own profile only, phone must be the verified one', async () => {
  await assertSucceeds(setDoc(doc(customer('c2', '+992900000002'), 'customers/c2'), profile('+992900000002')));
  await assertFails(setDoc(doc(customer('c2', '+992900000002'), 'customers/c2'), profile('+992999999999')));
  await assertFails(setDoc(doc(customer('c2', '+992900000002'), 'customers/c3'), profile('+992900000002')));
  await assertFails(setDoc(doc(customer('c2', '+992900000002'), 'customers/c2'), { ...profile('+992900000002'), discount: 99 }));
  await assertSucceeds(getDoc(doc(customer(), 'customers/c1')));
  await assertFails(getDoc(doc(customer('c2', '+992900000002'), 'customers/c1')));
  await assertFails(getDocs(collection(customer(), 'customers')));
  await assertFails(getDoc(doc(guest(), 'customers/c1')));
  await assertSucceeds(getDocs(collection(admin(), 'customers')));
});

test('personal account: customer sees only own orders', async () => {
  await assertSucceeds(getDocs(query(collection(customer(), 'orders'), where('uid', '==', 'c1'))));
  await assertSucceeds(getDoc(doc(customer(), 'orders/mine')));
  await assertFails(getDoc(doc(customer('c2', '+992900000002'), 'orders/mine')));
  await assertFails(getDocs(query(collection(customer('c2', '+992900000002'), 'orders'), where('uid', '==', 'c1'))));
  await assertSucceeds(setDoc(doc(customer(), 'orders/o9'), { status: 'new', uid: 'c1', customerCode: 'EVRO-AAAAAA' }));
  await assertFails(setDoc(doc(customer(), 'orders/o10'), { status: 'new', uid: 'c2' }));
  await assertFails(setDoc(doc(guest(), 'orders/o11'), { status: 'new', uid: 'c1' }));
  await assertFails(updateDoc(doc(customer(), 'orders/mine'), { status: 'cancelled' }));
});

test('unknown collections are closed', async () => {
  await assertFails(setDoc(doc(admin(), 'other/x'), { a: 1 }));
  await assertFails(getDoc(doc(guest(), 'other/x')));
});
