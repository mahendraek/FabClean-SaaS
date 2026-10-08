import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="sign-in" />
        <Stack.Screen name="services" />
        <Stack.Screen name="orders" />
        <Stack.Screen name="order-detail" />
        <Stack.Screen name="inspection" />
        <Stack.Screen name="customers" />
        <Stack.Screen name="customer-profile" />
        <Stack.Screen name="walk-in" />
        <Stack.Screen name="admin" />
        <Stack.Screen name="staff" />
        <Stack.Screen name="platform-admin" />
        <Stack.Screen name="brand-stores" />
        <Stack.Screen name="retention" />
        <Stack.Screen name="scheduling" />
        <Stack.Screen name="pickup-schedule" />
        <Stack.Screen name="subscriptions" />
        <Stack.Screen name="financial" />
        <Stack.Screen name="reports" />
        <Stack.Screen name="login-audit" />
        <Stack.Screen name="garment-tags" />
        <Stack.Screen name="garment-assembly" />
        <Stack.Screen name="hardware" />
      </Stack>
    </>
  );
}
