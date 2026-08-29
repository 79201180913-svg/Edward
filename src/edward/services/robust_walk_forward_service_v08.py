from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Any, Callable, Iterable, Sequence

from edward.services.analysis_service import Candle
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestResult, ResearchBacktestService
from edward.services.wf_parameter_stability_diagnostics_v08 import neighborhood_stability_pct, parameter_key, selection_confidence, winner_margin_pct
from edward.services.wf_parameter_transfer_service_v083 import ParameterTransferHistoryEntry, WFParameterTransferSelectorV083

ROBUST_WF_VERSION = "0.8.0"
logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class WalkForwardWindowResult:
    index: int
    train_start: Any
    train_end: Any
    test_start: Any
    test_end: Any
    parameters: dict[str, Any]
    train_score: float
    test_net_return_pct: float
    test_benchmark_return_pct: float
    test_excess_return_pct: float
    test_max_drawdown_pct: float
    test_sharpe: float
    test_sortino: float
    test_trades: int

@dataclass(frozen=True, slots=True)
class ParameterStability:
    windows: int
    dominant_windows: int
    stability_pct: float
    selected_parameters: tuple[tuple[tuple[str, Any], ...], ...]

@dataclass(frozen=True, slots=True)
class RobustWalkForwardResult:
    strategy: str
    windows: tuple[WalkForwardWindowResult, ...]
    mean_test_return_pct: float
    median_test_return_pct: float
    std_test_return_pct: float
    worst_test_return_pct: float
    best_test_return_pct: float
    mean_test_drawdown_pct: float
    mean_test_sharpe: float
    positive_return_windows: int
    risk_ok_windows: int
    positive_sharpe_windows: int
    return_consistency_pct: float
    risk_consistency_pct: float
    sharpe_consistency_pct: float
    robustness_score: float
    parameter_stability: ParameterStability
    version: str = ROBUST_WF_VERSION

class RobustWalkForwardService:
    """Rolling out-of-sample research with parameter/performance robustness."""
    @staticmethod
    def _parameter_key(parameters: dict[str, Any]) -> tuple[tuple[str, Any], ...]: return parameter_key(parameters)

    @classmethod
    def _parameter_stability(cls, windows: Sequence[WalkForwardWindowResult]) -> ParameterStability:
        selected = tuple(cls._parameter_key(item.parameters) for item in windows)
        if not selected: return ParameterStability(0, 0, 0.0, ())
        counts: dict[tuple[tuple[str, Any], ...], int] = {}
        for item in selected: counts[item] = counts.get(item, 0) + 1
        dominant = max(counts.values())
        return ParameterStability(len(selected), dominant, dominant / len(selected) * 100.0, selected)

    @staticmethod
    def _candidate_sort_key(item: tuple[dict[str, Any], ResearchBacktestResult]) -> tuple[float, float, float]:
        result = item[1]; return result.excess_return_pct, result.sharpe, -result.max_drawdown_pct

    @staticmethod
    def _criterion_key(criterion: str, result: ResearchBacktestResult) -> float:
        if criterion == "excess_return": return result.excess_return_pct
        if criterion == "sharpe": return result.sharpe
        if criterion == "sortino": return result.sortino
        if criterion == "return_dd": return result.net_return_pct / max(result.max_drawdown_pct, 1e-9)
        raise ValueError(f"Unknown selection diagnostic criterion: {criterion}")

    @classmethod
    def _diagnostic_composite_key(cls, result: ResearchBacktestResult, candidates: Sequence[ResearchBacktestResult]) -> float:
        scores=[]
        for criterion in ("excess_return","sharpe","sortino","return_dd"):
            values=[cls._criterion_key(criterion,item) for item in candidates]; ordered=sorted(set(values)); value=cls._criterion_key(criterion,result)
            scores.append((ordered.index(value)+1)/max(len(ordered),1))
        return mean(scores)

    @classmethod
    def _log_selection_criteria_diagnostics(cls, *, strategy, window_index, train_candidates, oos_candidates, production_selected_params):
        train_results=[r for _,r in train_candidates]; oos_by_key={cls._parameter_key(p):r for p,r in oos_candidates}; train_by_key={cls._parameter_key(p):r for p,r in train_candidates}; matches={}; gaps={}
        for criterion in ("excess_return","sharpe","sortino","return_dd","composite"):
            if criterion=="composite":
                train_values={k:cls._diagnostic_composite_key(r,train_results) for k,r in train_by_key.items()}; oos_results=list(oos_by_key.values()); oos_values={k:cls._diagnostic_composite_key(r,oos_results) for k,r in oos_by_key.items()}
            else:
                train_values={k:cls._criterion_key(criterion,r) for k,r in train_by_key.items()}; oos_values={k:cls._criterion_key(criterion,r) for k,r in oos_by_key.items()}
            train_key=max(train_values,key=train_values.get); oos_key=max(oos_values,key=oos_values.get); production_key=cls._parameter_key(production_selected_params); selected_oos=oos_by_key[production_key]; winner_oos=oos_by_key[oos_key]
            matches[criterion]=train_key==oos_key; gaps[criterion]=winner_oos.net_return_pct-selected_oos.net_return_pct
            logger.warning("[V083 WF SELECTION CRITERION] strategy=%s window=%d criterion=%s train_winner=%s oos_winner=%s production_selected=%s transfer_match=%s production_oos_return=%.4f criterion_oos_winner_return=%.4f selection_gap=%.4f",strategy,window_index,criterion,dict(train_key),dict(oos_key),production_selected_params,matches[criterion],selected_oos.net_return_pct,winner_oos.net_return_pct,gaps[criterion])
        return matches,gaps

    @classmethod
    def _log_parameter_stability(cls, *, strategy, window_index, candidates, selected_params):
        margin=winner_margin_pct(candidates); neighborhood,nearby_count=neighborhood_stability_pct(selected_params,candidates); confidence=selection_confidence(margin,neighborhood)
        logger.warning("[V083 WF SELECTION STABILITY] strategy=%s window=%d selected=%s winner_margin_pct=%.2f neighborhood_stability_pct=%.2f nearby_candidates=%d selection_confidence=%.2f",strategy,window_index,selected_params,margin,neighborhood,nearby_count,confidence)
        return margin,neighborhood,confidence

    @classmethod
    def _log_parameter_leaderboard(cls, *, strategy, window_index, candidates, selected_params):
        for rank,(params,result) in enumerate(sorted(candidates,key=cls._candidate_sort_key,reverse=True),1):
            logger.warning("[V083 WF LEADERBOARD] strategy=%s window=%d rank=%d selected=%s params=%s train_excess=%.4f sharpe=%.4f sortino=%.4f dd=%.4f trades=%d exposure=%.2f return=%.4f benchmark=%.4f turnover=%.2f win_rate=%.2f",strategy,window_index,rank,params==selected_params,params,result.excess_return_pct,result.sharpe,result.sortino,result.max_drawdown_pct,result.trades,result.exposure_pct,result.net_return_pct,result.benchmark_return_pct,result.turnover_pct,result.win_rate_pct)

    @staticmethod
    def _log_window_activity(*, strategy, window, test_result):
        logger.warning("[V083 WF ACTIVITY] strategy=%s window=%d active=%s trades=%d active_bars=%d exposure_pct=%.2f turnover_pct=%.2f oos_return=%.4f oos_excess=%.4f dd=%.4f sharpe=%.4f",strategy,window.index,test_result.trades>0,test_result.trades,max(0,round(test_result.exposure_pct/100*max(0,len(test_result.equity)-1))),test_result.exposure_pct,test_result.turnover_pct,window.test_net_return_pct,window.test_excess_return_pct,window.test_max_drawdown_pct,window.test_sharpe)

    @classmethod
    def _log_oos_parameter_transfer(cls, *, strategy, window_index, candidates, selected_params):
        ranked=sorted(candidates,key=lambda item:(item[1].net_return_pct,item[1].sharpe,-item[1].max_drawdown_pct),reverse=True); selected_rank=next((rank for rank,(p,_) in enumerate(ranked,1) if p==selected_params),None); selected_result=next((r for p,r in candidates if p==selected_params),None)
        if selected_result is None or selected_rank is None or not ranked:return False,0.0
        oos_winner_params,oos_winner_result=ranked[0]; gap=oos_winner_result.net_return_pct-selected_result.net_return_pct
        logger.warning("[V083 WF OOS TRANSFER] strategy=%s window=%d train_selected=%s train_selected_oos_rank=%d oos_winner=%s transfer_match=%s selected_oos_return=%.4f oos_winner_return=%.4f selection_gap=%.4f selected_oos_sharpe=%.4f oos_winner_sharpe=%.4f selected_oos_dd=%.4f oos_winner_dd=%.4f",strategy,window_index,selected_params,selected_rank,oos_winner_params,selected_params==oos_winner_params,selected_result.net_return_pct,oos_winner_result.net_return_pct,gap,selected_result.sharpe,oos_winner_result.sharpe,selected_result.max_drawdown_pct,oos_winner_result.max_drawdown_pct)
        return selected_params==oos_winner_params,gap

    @classmethod
    def _log_parameter_transfer_shadow(cls, *, strategy, window_index, candidates, oos_candidates, baseline_parameters, history):
        selection=WFParameterTransferSelectorV083.select_with_history(candidates,history=history,baseline_parameters=baseline_parameters); oos_by_key={cls._parameter_key(p):r for p,r in oos_candidates}; baseline_key=cls._parameter_key(baseline_parameters); shadow_key=cls._parameter_key(selection.selected_parameters); baseline_oos=oos_by_key[baseline_key]; shadow_oos=oos_by_key[shadow_key]; changed=shadow_key!=baseline_key; delta=shadow_oos.net_return_pct-baseline_oos.net_return_pct
        logger.warning("[V083 WF TRANSFER SHADOW WINDOW] strategy=%s window=%d history_windows=%d baseline=%s shadow=%s changed=%s baseline_oos_return=%.4f shadow_oos_return=%.4f delta=%.4f baseline_rank=%d shadow_rank=%d baseline_sharpe=%.4f shadow_sharpe=%.4f baseline_dd=%.4f shadow_dd=%.4f",strategy,window_index,len(history),baseline_parameters,selection.selected_parameters,changed,baseline_oos.net_return_pct,shadow_oos.net_return_pct,delta,cls._oos_rank(oos_candidates,baseline_parameters),cls._oos_rank(oos_candidates,selection.selected_parameters),baseline_oos.sharpe,shadow_oos.sharpe,baseline_oos.max_drawdown_pct,shadow_oos.max_drawdown_pct)
        return dict(selection.selected_parameters),changed,delta

    @classmethod
    def _oos_rank(cls,candidates,parameters):
        ranked=sorted(candidates,key=lambda item:(item[1].net_return_pct,item[1].sharpe,-item[1].max_drawdown_pct),reverse=True); target=cls._parameter_key(parameters)
        return next(rank for rank,(params,_) in enumerate(ranked,1) if cls._parameter_key(params)==target)

    @classmethod
    def _append_oos_candidate_history(cls, *, strategy, window_index, oos_candidates, selection_confidence_value, history):
        """Append complete current-window OOS evidence only after shadow selection."""
        for params, result in oos_candidates:
            history.append(ParameterTransferHistoryEntry(window_index=window_index,parameters=dict(params),oos_net_return_pct=result.net_return_pct,oos_sharpe=result.sharpe,oos_drawdown_pct=result.max_drawdown_pct,selection_confidence=selection_confidence_value))
        logger.warning("[V083 WF TRANSFER HISTORY AUDIT APPEND] strategy=%s window=%d candidates_appended=%d history_entries=%d",strategy,window_index,len(oos_candidates),len(history))

    @classmethod
    def run(cls, *, candles: Iterable[Candle], strategy: str, parameter_grid: Sequence[dict[str, Any]], signal_factory: Callable[[str, dict[str, Any]], Callable[[Sequence[Candle], int], bool]], train_size: int, test_size: int, costs: BacktestCostModel | None = None, max_drawdown_pct: float | None = None) -> RobustWalkForwardResult:
        ordered=sorted(list(candles),key=lambda item:item.timestamp)
        if train_size<2 or test_size<1: raise ValueError("train_size must be >= 2 and test_size must be >= 1")
        if not parameter_grid: raise ValueError("parameter_grid cannot be empty")
        expected_windows=max(0,(len(ordered)-train_size)//test_size); logger.warning("[V083 WF START] strategy=%s candles=%d train=%d test=%d expected_windows=%d grid=%d max_dd=%s",strategy,len(ordered),train_size,test_size,expected_windows,len(parameter_grid),max_drawdown_pct)
        windows=[]; exposures=[]; transfer_matches=0; transfer_gaps=[]; criterion_matches={key:0 for key in ("excess_return","sharpe","sortino","return_dd","composite")}; criterion_gaps={key:[] for key in criterion_matches}; stability_margins=[]; stability_neighborhoods=[]; stability_confidences=[]; shadow_changed=0; shadow_deltas=[]; history=[]; start=0
        while start+train_size+test_size<=len(ordered):
            train=ordered[start:start+train_size]; test=ordered[start+train_size:start+train_size+test_size]; window_index=len(windows); candidates=[]
            for params in parameter_grid:
                train_result=ResearchBacktestService.run(candles=train,strategy=strategy,parameters=params,signal_fn=signal_factory(strategy,params),costs=costs); candidates.append((dict(params),train_result))
            selected_params,train_result=max(candidates,key=cls._candidate_sort_key); cls._log_parameter_leaderboard(strategy=strategy,window_index=window_index,candidates=candidates,selected_params=selected_params); margin,neighborhood,confidence=cls._log_parameter_stability(strategy=strategy,window_index=window_index,candidates=candidates,selected_params=selected_params); stability_margins.append(margin); stability_neighborhoods.append(neighborhood); stability_confidences.append(confidence)
            oos_candidates=[]
            for params,_ in candidates:
                oos_result=ResearchBacktestService.run(candles=test,strategy=strategy,parameters=params,signal_fn=signal_factory(strategy,params),costs=costs); oos_candidates.append((dict(params),oos_result))
            matches,gaps=cls._log_selection_criteria_diagnostics(strategy=strategy,window_index=window_index,train_candidates=candidates,oos_candidates=oos_candidates,production_selected_params=selected_params)
            for criterion,matched in matches.items(): criterion_matches[criterion]+=int(matched); criterion_gaps[criterion].append(gaps[criterion])
            transfer_match,transfer_gap=cls._log_oos_parameter_transfer(strategy=strategy,window_index=window_index,candidates=oos_candidates,selected_params=selected_params)
            if transfer_match: transfer_matches+=1
            transfer_gaps.append(transfer_gap)
            _,changed,shadow_delta=cls._log_parameter_transfer_shadow(strategy=strategy,window_index=window_index,candidates=candidates,oos_candidates=oos_candidates,baseline_parameters=selected_params,history=history)
            if changed: shadow_changed+=1
            shadow_deltas.append(shadow_delta)
            test_result=next(result for params,result in oos_candidates if params==selected_params); exposures.append(test_result.exposure_pct)
            window=WalkForwardWindowResult(window_index,train[0].timestamp,train[-1].timestamp,test[0].timestamp,test[-1].timestamp,dict(selected_params),train_result.excess_return_pct,test_result.net_return_pct,test_result.benchmark_return_pct,test_result.excess_return_pct,test_result.max_drawdown_pct,test_result.sharpe,test_result.sortino,test_result.trades); windows.append(window)
            cls._append_oos_candidate_history(strategy=strategy,window_index=window_index,oos_candidates=oos_candidates,selection_confidence_value=confidence,history=history)
            logger.warning("[V083 WF WINDOW] strategy=%s window=%d train=%s..%s test=%s..%s params=%s train_excess=%.4f oos_return=%.4f benchmark=%.4f excess=%.4f dd=%.4f sharpe=%.4f sortino=%.4f trades=%d",strategy,window.index,window.train_start,window.train_end,window.test_start,window.test_end,window.parameters,window.train_score,window.test_net_return_pct,window.test_benchmark_return_pct,window.test_excess_return_pct,window.test_max_drawdown_pct,window.test_sharpe,window.test_sortino,window.test_trades); cls._log_window_activity(strategy=strategy,window=window,test_result=test_result); start+=test_size
        if not windows: logger.warning("[V083 WF EMPTY] strategy=%s candles=%d train=%d test=%d",strategy,len(ordered),train_size,test_size); return cls._empty(strategy)
        returns=[i.test_net_return_pct for i in windows]; drawdowns=[i.test_max_drawdown_pct for i in windows]; sharpes=[i.test_sharpe for i in windows]; count=len(windows); positive=sum(v>0 for v in returns); risk_ok=sum(max_drawdown_pct is None or v<=max_drawdown_pct for v in drawdowns); positive_sharpe=sum(v>0 for v in sharpes); return_consistency=positive/count*100; risk_consistency=risk_ok/count*100; sharpe_consistency=positive_sharpe/count*100; stability=cls._parameter_stability(windows); dispersion_penalty=pstdev(returns)/max(abs(mean(returns)),1.0)*10; performance_consistency=max(0.0,min(100.0,100.0-dispersion_penalty)); robustness=round(return_consistency*.35+risk_consistency*.20+sharpe_consistency*.15+stability.stability_pct*.15+performance_consistency*.15,2)
        result=RobustWalkForwardResult(strategy=strategy,windows=tuple(windows),mean_test_return_pct=mean(returns),median_test_return_pct=median(returns),std_test_return_pct=pstdev(returns) if len(returns)>1 else 0.0,worst_test_return_pct=min(returns),best_test_return_pct=max(returns),mean_test_drawdown_pct=mean(drawdowns),mean_test_sharpe=mean(sharpes),positive_return_windows=positive,risk_ok_windows=risk_ok,positive_sharpe_windows=positive_sharpe,return_consistency_pct=return_consistency,risk_consistency_pct=risk_consistency,sharpe_consistency_pct=sharpe_consistency,robustness_score=robustness,parameter_stability=stability)
        active_windows=sum(i.test_trades>0 for i in windows); logger.warning("[V083 WF ACTIVITY RESULT] strategy=%s windows=%d active_windows=%d inactive_windows=%d active_pct=%.2f total_trades=%d mean_exposure=%.2f",strategy,count,active_windows,count-active_windows,active_windows/count*100,sum(i.test_trades for i in windows),mean(exposures)); logger.warning("[V083 WF TRANSFER RESULT] strategy=%s windows=%d transfer_matches=%d transfer_match_pct=%.2f mean_oos_selection_gap=%.4f max_oos_selection_gap=%.4f",strategy,count,transfer_matches,transfer_matches/count*100,mean(transfer_gaps) if transfer_gaps else 0,max(transfer_gaps) if transfer_gaps else 0); logger.warning("[V083 WF TRANSFER SHADOW RESULT] strategy=%s windows=%d changed_windows=%d changed_pct=%.2f mean_return_delta=%.4f positive_delta_windows=%d",strategy,count,shadow_changed,shadow_changed/count*100,mean(shadow_deltas) if shadow_deltas else 0,sum(d>0 for d in shadow_deltas));
        for criterion in criterion_matches:
            gaps=criterion_gaps[criterion]; logger.warning("[V083 WF SELECTION RESULT] strategy=%s criterion=%s transfer_matches=%d transfer_match_pct=%.2f mean_oos_selection_gap=%.4f max_oos_selection_gap=%.4f",strategy,criterion,criterion_matches[criterion],criterion_matches[criterion]/count*100,mean(gaps) if gaps else 0,max(gaps) if gaps else 0)
        logger.warning("[V083 WF SELECTION STABILITY RESULT] strategy=%s windows=%d mean_winner_margin_pct=%.2f mean_neighborhood_stability_pct=%.2f mean_selection_confidence=%.2f",strategy,count,mean(stability_margins),mean(stability_neighborhoods),mean(stability_confidences)); logger.warning("[V083 WF RESULT] strategy=%s windows=%d mean_return=%.4f median_return=%.4f std_return=%.4f worst_return=%.4f best_return=%.4f mean_dd=%.4f mean_sharpe=%.4f positive=%d/%d risk_ok=%d/%d positive_sharpe=%d/%d return_consistency=%.2f risk_consistency=%.2f sharpe_consistency=%.2f parameter_stability=%.2f robustness=%.2f",strategy,count,result.mean_test_return_pct,result.median_test_return_pct,result.std_test_return_pct,result.worst_test_return_pct,result.best_test_return_pct,result.mean_test_drawdown_pct,result.mean_test_sharpe,result.positive_return_windows,count,result.risk_ok_windows,count,result.positive_sharpe_windows,count,result.return_consistency_pct,result.risk_consistency_pct,result.sharpe_consistency_pct,result.parameter_stability.stability_pct,result.robustness_score); return result

    @staticmethod
    def _empty(strategy: str) -> RobustWalkForwardResult: return RobustWalkForwardResult(strategy,(),0.0,0.0,0.0,0.0,0.0,0.0,0,0,0,0.0,0.0,0.0,0.0,ParameterStability(0,0,0.0,()))

__all__=["ROBUST_WF_VERSION","WalkForwardWindowResult","ParameterStability","RobustWalkForwardResult","RobustWalkForwardService"]