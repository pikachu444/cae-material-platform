/**
 * The registered Materials hotspot is the only remaining consumer. Remove
 * this compatibility entry when #262 extracts Materials/Activity composition;
 * all Modeling-owned consumers import features/modeling directly.
 */
export {
  loadModelingSession,
  saveModelingSession,
} from "./features/modeling/model/session-controller";
