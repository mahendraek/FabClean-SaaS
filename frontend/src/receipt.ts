import { api } from "@/src/api";
import { code128Svg } from "@/src/hardware";

function esc(v:any){
  return String(v??"")
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;");
}

function money(v:any){return "$"+Number(v||0).toFixed(2);}

export async function printOrderReceipt(orderId:string){
  if(typeof window==="undefined")return;
  const [receipt,settings,garmentResult]=await Promise.all([
    api.get<any>("/orders/"+encodeURIComponent(orderId)+"/receipt"),
    api.get<any>("/settings"),
    api.get<any>("/orders/"+encodeURIComponent(orderId)+"/garments")
  ]);

  const order=receipt.order||{};
  const customer=order.customer||{};
  const items=order.items||[];
  const garments=garmentResult.garments||[];
  const businessName=settings.business_name||receipt.business_name||"FabClean";
  const businessAddress=settings.business_address||"";
  const businessPhone=settings.business_phone||"";
  const receiptNo=receipt.receipt_number||order.order_number||"Receipt";
  const orderCode=order.barcode_value||String(order.order_number||"").replace("-","");

  const itemRows=items.map((item:any,index:number)=>{
    const lineTotal=Number(item.quantity||0)*Number(item.unit_price||0);
    return `<tr>
      <td>${index+1}</td>
      <td><strong>${esc(item.service_name||"Service")}</strong>${item.notes?`<div class="muted">${esc(item.notes)}</div>`:""}</td>
      <td class="num">${esc(item.quantity)}</td>
      <td class="num">${money(item.unit_price)}</td>
      <td class="num">${money(lineTotal)}</td>
    </tr>`;
  }).join("");

  const garmentRows=garments.map((g:any,index:number)=>`<div class="garment">
    <div class="garment-head"><strong>${index+1}. ${esc(g.service_name||"Garment")}</strong><span>${esc(g.garment_code)}</span></div>
    <div class="mini-barcode">${code128Svg(g.garment_code,38,1.2)}</div>
  </div>`).join("");

  const w=window.open("","_blank","width=760,height=900");
  if(!w)throw new Error("Pop-up blocked. Allow pop-ups to print the receipt.");

  w.document.write(`<!doctype html>
<html>
<head>
  <title>${esc(receiptNo)}</title>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <style>
    @page{margin:10mm}
    *{box-sizing:border-box}
    body{font-family:Arial,Helvetica,sans-serif;color:#111;margin:0;background:#fff}
    .receipt{max-width:760px;margin:0 auto;padding:18px}
    .business{text-align:center}
    .business h1{font-size:24px;margin:0 0 5px}
    .business div{font-size:13px;line-height:1.45}
    .order-barcode{margin:16px auto 12px;text-align:center;overflow:hidden}
    .order-barcode svg{max-width:100%;height:64px}
    .barcode-text{font-size:12px;font-weight:700;letter-spacing:.8px;margin-top:3px}
    .rule{border-top:1px solid #222;margin:14px 0}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
    .section h3{font-size:12px;text-transform:uppercase;letter-spacing:.8px;margin:0 0 6px}
    .section div{font-size:13px;line-height:1.45}
    table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}
    th,td{padding:8px 6px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}
    th{font-size:11px;text-transform:uppercase}
    .num{text-align:right;white-space:nowrap}
    .summary{margin-left:auto;width:min(340px,100%);margin-top:12px}
    .sumrow{display:flex;justify-content:space-between;padding:4px 0;font-size:13px}
    .sumrow.total{font-size:17px;font-weight:700;border-top:1px solid #222;margin-top:5px;padding-top:8px}
    .muted{color:#666;font-size:11px;margin-top:2px}
    .garments{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
    .garment{border:1px solid #ddd;border-radius:8px;padding:8px;break-inside:avoid}
    .garment-head{display:flex;justify-content:space-between;gap:8px;font-size:11px}
    .mini-barcode{overflow:hidden;text-align:center;margin-top:6px}
    .mini-barcode svg{max-width:100%;height:38px}
    .footer{text-align:center;color:#555;font-size:11px;margin-top:18px}
    .print-actions{text-align:center;margin:16px 0}
    button{padding:10px 16px;font-weight:700}
    @media(max-width:560px){.grid{grid-template-columns:1fr}.garments{grid-template-columns:1fr}.receipt{padding:10px}}
    @media print{.print-actions{display:none}.receipt{padding:0}}
  </style>
</head>
<body>
  <div class="receipt">
    <div class="business">
      <h1>${esc(businessName)}</h1>
      ${businessAddress?`<div>${esc(businessAddress)}</div>`:""}
      ${businessPhone?`<div>Phone: ${esc(businessPhone)}</div>`:""}
    </div>

    <div class="order-barcode">
      ${code128Svg(orderCode,64,1.7)}
      <div class="barcode-text">${esc(order.order_number)} · ${esc(orderCode)}</div>
    </div>

    <div class="rule"></div>
    <div class="grid">
      <div class="section">
        <h3>Customer</h3>
        <div><strong>${esc(customer.name)}</strong></div>
        <div>${esc(customer.phone)}</div>
        ${customer.email?`<div>${esc(customer.email)}</div>`:""}
      </div>
      <div class="section">
        <h3>Order</h3>
        <div>Order #: <strong>${esc(order.order_number)}</strong></div>
        <div>Receipt #: ${esc(receiptNo)}</div>
        <div>Status: ${esc(order.status||"received")}</div>
        <div>Fulfillment: ${esc(String(order.fulfillment_type||"walk_in").replaceAll("_"," "))}</div>
        ${order.due_at?`<div>Due: ${esc(order.due_at)}</div>`:""}
      </div>
    </div>

    <div class="rule"></div>
    <div class="section">
      <h3>Detailed inventory</h3>
      <table>
        <thead><tr><th>#</th><th>Garment / Service</th><th class="num">Qty</th><th class="num">Unit</th><th class="num">Amount</th></tr></thead>
        <tbody>${itemRows}</tbody>
      </table>
    </div>

    <div class="summary">
      <div class="sumrow"><span>Subtotal</span><span>${money(order.subtotal)}</span></div>
      ${Number(order.discount||0)?`<div class="sumrow"><span>Discount</span><span>-${money(order.discount)}</span></div>`:""}
      ${Number(order.tax||0)?`<div class="sumrow"><span>Tax</span><span>${money(order.tax)}</span></div>`:""}
      ${Number(order.delivery_fee||0)?`<div class="sumrow"><span>Pickup / Delivery</span><span>${money(order.delivery_fee)}</span></div>`:""}
      <div class="sumrow total"><span>Total</span><span>${money(order.total)}</span></div>
      <div class="sumrow"><span>Paid</span><span>${money(receipt.paid_total)}</span></div>
      <div class="sumrow"><span>Balance</span><span>${money(receipt.balance_due)}</span></div>
    </div>

    ${garments.length?`<div class="rule"></div><div class="section"><h3>Individual garment barcodes (${garments.length})</h3><div class="garments">${garmentRows}</div></div>`:""}

    ${order.notes?`<div class="rule"></div><div class="section"><h3>Order notes</h3><div>${esc(order.notes)}</div></div>`:""}

    <div class="footer">Thank you for choosing ${esc(businessName)}.</div>
    <div class="print-actions"><button onclick="window.print()">Print Receipt</button></div>
  </div>
</body>
</html>`);
  w.document.close();
}
