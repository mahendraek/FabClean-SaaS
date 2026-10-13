export type MapPoint = { latitude: number; longitude: number };
export type CoverageZone = { id: string; name: string; pickup: boolean; delivery: boolean; active: boolean; vertices: MapPoint[] };
export type CoveragePolicy = { enabled: boolean; mode: 'radius'|'zones'; unit: 'mi'|'km'; radius: number; zones: CoverageZone[] };
export const MAX_LAT=85.05112878;
export function coordinate(text:string,latitude=true):number {
  const value=Number(text),limit=latitude?MAX_LAT:180;
  if(!text.trim()||!Number.isFinite(value)||Math.abs(value)>limit)throw new Error('Enter valid latitude and longitude');
  return value;
}
export function project(p:MapPoint,zoom:number){
  const size=256*2**zoom,lat=Math.max(-MAX_LAT,Math.min(MAX_LAT,p.latitude))*Math.PI/180;
  return {x:(p.longitude+180)/360*size,y:(1-Math.log(Math.tan(Math.PI/4+lat/2))/Math.PI)/2*size};
}
export function unproject(x:number,y:number,zoom:number):MapPoint {
  const size=256*2**zoom,wrapped=(x%size+size)%size,clamped=Math.max(0,Math.min(size,y));
  return {longitude:wrapped/size*360-180,latitude:Math.atan(Math.sinh(Math.PI*(1-2*clamped/size)))*180/Math.PI};
}
export function radiusKm(policy:CoveragePolicy){return policy.radius*(policy.unit==='mi'?1.609344:1);}
export function convertUnit(policy:CoveragePolicy,unit:'mi'|'km'):CoveragePolicy {
  return {...policy,unit,radius:Number((radiusKm(policy)/(unit==='mi'?1.609344:1)).toFixed(6))};
}
export function circle(center:MapPoint,km:number):MapPoint[]{
  const lat=center.latitude*Math.PI/180,lon=center.longitude*Math.PI/180,angle=km/6371.0088;
  return Array.from({length:64},(_,i)=>{const bearing=i*2*Math.PI/64;const latitude=Math.asin(Math.sin(lat)*Math.cos(angle)+Math.cos(lat)*Math.sin(angle)*Math.cos(bearing));const longitude=lon+Math.atan2(Math.sin(bearing)*Math.sin(angle)*Math.cos(lat),Math.cos(angle)-Math.sin(lat)*Math.sin(latitude));return {latitude:latitude*180/Math.PI,longitude:((longitude*180/Math.PI+540)%360)-180};});
}
