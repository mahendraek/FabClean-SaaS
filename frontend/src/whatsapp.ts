/** Manual click-to-chat link. Opening it never confirms sending or delivery. */
export function whatsappReceiptURL(phone: string, message: string): string {
  if (!/^\+[1-9]\d{7,14}$/.test(phone)) throw new Error("Use an international phone number with its country code.");
  if (!message.trim()) throw new Error("The receipt message is empty.");
  const encoded = encodeURIComponent(message);
  if (encoded.replace(/%[0-9A-F]{2}/g, "x").length > 6000) throw new Error("This receipt is too long for WhatsApp link sharing.");
  return "https://wa.me/"+phone.slice(1)+"?text="+encoded;
}
