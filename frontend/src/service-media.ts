export const serviceImages: Record<string, string> = {
  "Laundry": "https://d2ol7oe51mr4n9.cloudfront.net/user_3JBACPYVE2mj8wEzf9h14CXTmnp/3a6e18aa-5bfe-43ae-9673-1806e326e02e.jpg",
  "Wash & Fold": "https://d2ol7oe51mr4n9.cloudfront.net/user_3JBACPYVE2mj8wEzf9h14CXTmnp/3a6e18aa-5bfe-43ae-9673-1806e326e02e.jpg",
  "Dry Cleaning": "https://d2ol7oe51mr4n9.cloudfront.net/user_3JBACPYVE2mj8wEzf9h14CXTmnp/6380441d-2690-473d-abdb-d3847d6e728c.jpg",
  "Shoes": "https://d2ol7oe51mr4n9.cloudfront.net/user_3JBACPYVE2mj8wEzf9h14CXTmnp/671ba330-7fce-4880-8646-532956658aff.jpg",
  "Bags": "https://d2ol7oe51mr4n9.cloudfront.net/user_3JBACPYVE2mj8wEzf9h14CXTmnp/3f62266b-0914-4f12-8c22-2793aee95b9d.jpg",
  "Curtains": "https://d2ol7oe51mr4n9.cloudfront.net/user_3JBACPYVE2mj8wEzf9h14CXTmnp/649eb81e-91b0-4455-95fe-974b127867b2.jpg",
  "Household": "https://d2ol7oe51mr4n9.cloudfront.net/user_3JBACPYVE2mj8wEzf9h14CXTmnp/d7f7a9a0-26ed-49a0-a9be-bf117e5027df.jpg",
  "Bedding": "https://d2ol7oe51mr4n9.cloudfront.net/user_3JBACPYVE2mj8wEzf9h14CXTmnp/d7f7a9a0-26ed-49a0-a9be-bf117e5027df.jpg",
};

export function imageForCategory(category: string) {
  return serviceImages[category] || serviceImages["Laundry"];
}

// deployment refresh
