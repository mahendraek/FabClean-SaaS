import { useBrandTheme } from "@/src/theme";
import { Stack } from "expo-router";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";

import { InvitationTokenProvider } from "@/src/InvitationToken";
import { ActiveContext } from "@/src/ActiveContext";

export default function RootLayout() {
  const themeVersion=useBrandTheme();
  return (
    <SafeAreaProvider><SafeAreaView style={{ flex: 1 }} edges={["top", "left", "right"]}>
      <StatusBar style="dark" />
      <InvitationTokenProvider><ActiveContext>{key => <Stack key={key+":"+themeVersion} screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="sign-in" />
        <Stack.Screen name="accept-invite" />
        <Stack.Screen name="services" />
        <Stack.Screen name="orders" />
        <Stack.Screen name="handoffs" />
        <Stack.Screen name="order-detail" />
        <Stack.Screen name="inspection" />
        <Stack.Screen name="customers" />
        <Stack.Screen name="customer-profile" />
        <Stack.Screen name="walk-in" />
        <Stack.Screen name="admin" />
        <Stack.Screen name="configuration" />
        <Stack.Screen name="notifications" />
        <Stack.Screen name="coverage" />
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
        <Stack.Screen name="taxes" />
        <Stack.Screen name="print-preview" />
      </Stack>}</ActiveContext></InvitationTokenProvider>
    </SafeAreaView></SafeAreaProvider>
  );
}
