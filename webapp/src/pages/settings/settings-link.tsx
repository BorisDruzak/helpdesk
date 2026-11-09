import type {AnchorHTMLAttributes} from 'react';
import {Link,useInRouterContext} from 'react-router-dom';

// Internal navigation must pass through the router's unsaved-draft blocker.
export function SettingsLink({href,children,...props}:AnchorHTMLAttributes<HTMLAnchorElement>&{href:string}) {
 return useInRouterContext()?<Link to={href} {...props}>{children}</Link>:<a href={href} {...props}>{children}</a>;
}
