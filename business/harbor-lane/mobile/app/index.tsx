import { Link } from "expo-router";
import { StyleSheet, Text, View, Pressable } from "react-native";

export default function HomeScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Harbor Lane Advisory</Text>
      <Text style={styles.subtitle}>Client app — jobs, invoices, messages</Text>
      <View style={styles.nav}>
        <Link href="/projects" asChild>
          <Pressable style={styles.card}>
            <Text style={styles.cardTitle}>Projects</Text>
            <Text style={styles.cardBody}>Active jobs and retainers</Text>
          </Pressable>
        </Link>
        <Link href="/invoices" asChild>
          <Pressable style={styles.card}>
            <Text style={styles.cardTitle}>Invoices</Text>
            <Text style={styles.cardBody}>Payment status</Text>
          </Pressable>
        </Link>
        <Link href="/messages" asChild>
          <Pressable style={styles.card}>
            <Text style={styles.cardTitle}>Messages</Text>
            <Text style={styles.cardBody}>Contact your account team</Text>
          </Pressable>
        </Link>
      </View>
      <Text style={styles.footer}>
        support@harborlane.qenex.dev
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fafbfc", padding: 24, paddingTop: 48 },
  title: { fontSize: 24, fontWeight: "700", color: "#152935" },
  subtitle: { marginTop: 8, fontSize: 14, color: "#64748b" },
  nav: { marginTop: 32, gap: 12 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  cardTitle: { fontSize: 16, fontWeight: "600", color: "#295a6f" },
  cardBody: { marginTop: 4, fontSize: 13, color: "#64748b" },
  footer: { marginTop: "auto", textAlign: "center", fontSize: 12, color: "#94a3b8" },
});
