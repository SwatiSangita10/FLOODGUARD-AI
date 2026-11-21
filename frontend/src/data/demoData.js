// DEMO DATA ONLY. These illustrative values are not live observations,
// verified incidents, resource inventories, or AI-generated predictions.
export const demoLocations = {
  Bhubaneswar: {
    region: 'Odisha, India',
    risk: 'Moderate',
    riskScore: '58 / 100',
    reports: 4,
    alerts: 2,
    resources: 12,
  },
}

export const demoAlerts = [
  { level: 'critical', title: 'Canal-side road closure', detail: 'Illustrative scenario · pending verification', time: 'Demo alert' },
  { level: 'watch', title: 'Heavy rainfall watch', detail: 'Sample notice · not a live weather warning', time: 'Demo alert' },
]

export const demoReports = [
  { id: 'FG-D01', area: 'Unit 6 · sample location', type: 'Waterlogging', status: 'Pending review', updated: 'Demo record' },
  { id: 'FG-D02', area: 'Old Town · sample location', type: 'Road obstruction', status: 'Unverified', updated: 'Demo record' },
  { id: 'FG-D03', area: 'Saheed Nagar · sample location', type: 'Rising water', status: 'Pending review', updated: 'Demo record' },
]

export const demoResources = [
  { name: 'Community relief point', category: 'Shelter', area: 'Sample address · Bhubaneswar', availability: 'Unconfirmed', icon: 'house' },
  { name: 'Water distribution desk', category: 'Drinking water', area: 'Sample address · Bhubaneswar', availability: 'Unconfirmed', icon: 'droplet' },
  { name: 'First aid support point', category: 'Medical', area: 'Sample address · Bhubaneswar', availability: 'Unconfirmed', icon: 'medical' },
  { name: 'Food supply collection', category: 'Food', area: 'Sample address · Bhubaneswar', availability: 'Unconfirmed', icon: 'food' },
]
