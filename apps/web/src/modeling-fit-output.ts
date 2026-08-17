/**
 * Compatibility entry for the workbench's existing lazy Fit restore chunk.
 * The implementation is owned by Modeling; remove this bridge when #263 moves
 * the remaining root frontend entry points.
 */
export {
  parseExactSavedFitOutput,
  readVerifiedExactOutput,
} from "./features/modeling/model/fit-output";
