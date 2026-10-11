export type LaunchFeature = { id:string; name:string; description:string; weeks:number; points:number; fit:Record<string,number>; pattern:RegExp };
export const features:LaunchFeature[] = [
 {id:'funnels',name:'Funnels & conversion tracking',description:'Measure signup, activation, and checkout drop-off with custom events.',weeks:4,points:8,fit:{startup:1,agency:.8,enterprise:.7},pattern:/funnel|conversion|custom event/i},
 {id:'reports',name:'Client reporting & white label',description:'Scheduled branded reports, client workspaces, and shareable dashboards.',weeks:3,points:7,fit:{startup:.4,agency:1,enterprise:.6},pattern:/white.label|report|dashboard/i},
 {id:'integrations',name:'API & data integrations',description:'Export data to a warehouse or BI tool with API keys and usage limits.',weeks:4,points:7,fit:{startup:.7,agency:.8,enterprise:1},pattern:/\bapi\b|integration|export|warehouse/i},
 {id:'sso',name:'SSO & role-based access',description:'SAML sign-in, scoped permissions, and an audit trail for larger teams.',weeks:5,points:9,fit:{startup:.2,agency:.5,enterprise:1},pattern:/sso|saml|role.based|audit/i},
 {id:'onboarding',name:'Guided setup & migration',description:'Import existing data, validate installation, and guide the first useful workflow.',weeks:2,points:6,fit:{startup:1,agency:.8,enterprise:.5},pattern:/import|migration|onboarding|setup/i},
 {id:'alerts',name:'Automated alerts & summaries',description:'Configurable thresholds, anomaly notifications, and digest emails.',weeks:3,points:6,fit:{startup:.8,agency:1,enterprise:.7},pattern:/alert|anomal|notification|digest/i},
];
export type LaunchPlan={selected:string[];segment:string;adoption:number;readiness:number;budget:number;weeks:Record<string,number>;points:Record<string,number>};
export const defaultPlan:LaunchPlan={selected:[],segment:'startup',adoption:50,readiness:80,budget:8,weeks:{},points:{}};
export function launchImpact(plan:LaunchPlan){
 const chosen=features.filter(f=>plan.selected.includes(f.id));
 const effort=chosen.reduce((n,f)=>n+Math.max(1,plan.weeks[f.id]??f.weeks),0);
 const delivery=effort?Math.min(1,Math.max(0,plan.budget)/effort):1;
 const potential=chosen.reduce((n,f)=>n+Math.max(0,plan.points[f.id]??f.points)*(f.fit[plan.segment]??.5),0);
 return {effort,delivery,potential,lift:Math.min(40,potential* Math.max(0,Math.min(100,plan.adoption))/100*Math.max(0,Math.min(100,plan.readiness))/100*delivery)};
}
