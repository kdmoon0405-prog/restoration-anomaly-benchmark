import pytest
from types import SimpleNamespace
from scripts import profile_patchcore_stages as profiling
from scripts.profile_patchcore_stages import cost_simulation
from scripts.summarize_profiling_readiness import planning_estimate


def test_conditional_cost_is_simulation_with_correct_break_even():
    result = cost_simulation(2., 1., 3.)
    assert result["break_even_call_fraction"] == .5
    assert result["rows"][2]["savings_seconds"] == 0
    assert result["rows"][-1]["conditional_seconds"] == 6
    assert result["rows"][-1]["savings_fraction"] == -.5
    with pytest.raises(ValueError):
        cost_simulation(1., 0., 0.)


def test_instrumentation_preserves_detach_shapes_and_restores_on_error(monkeypatch):
    calls = []

    class Feature:
        def detach(self):
            calls.append("detach")
            return self

        def cpu(self):
            calls.append("cpu")
            return self

        def numpy(self):
            calls.append("numpy")
            return [1., 2.]

    class Model:
        def _embed(self, images, detach=True, provide_patch_shapes=False):
            calls.append((images, detach, provide_patch_shapes))
            features = [Feature()]
            return (features, [(2, 2)]) if provide_patch_shapes else features

    model = Model()
    echo = lambda *args, **kwargs: (args, kwargs)
    model.anomaly_scorer = SimpleNamespace(nn_method=SimpleNamespace(run=echo))
    model.patch_maker = SimpleNamespace(unpatch_scores=echo, score=echo)
    model.anomaly_segmentor = SimpleNamespace(convert_to_segmentation=echo)
    targets = [(model, "_embed"), (model.anomaly_scorer.nn_method, "run"),
               (model.patch_maker, "unpatch_scores"), (model.patch_maker, "score"),
               (model.anomaly_segmentor, "convert_to_segmentation")]
    originals = [getattr(obj, name) for obj, name in targets]
    monkeypatch.setattr(profiling, "start_timer", lambda *args: 0.)
    monkeypatch.setattr(profiling, "elapsed_seconds", lambda *args: 1.)
    stages = {}
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with profiling.instrument(model, None, "cpu", stages):
            features, shapes = model._embed("batch", provide_patch_shapes=True)
            assert features == [[1., 2.]] and shapes == [(2, 2)]
            assert calls == [("batch", False, True), "detach", "cpu", "numpy"]
            assert isinstance(model._embed("batch", detach=False)[0], Feature)
            assert model.anomaly_scorer.nn_method.run("query", k=1) == (("query",), {"k": 1})
            model.patch_maker.unpatch_scores(1)
            model.patch_maker.score(2)
            model.anomaly_segmentor.convert_to_segmentation(3)
            raise RuntimeError("synthetic failure")
    assert [getattr(obj, name) for obj, name in targets] == originals
    assert stages == {"backbone_embedding_seconds": 2., "feature_detach_cpu_numpy_seconds": 1.,
                      "faiss_search_seconds": 1., "score_map_postprocessing_seconds": 3.}


def test_pcb_resource_reference_scales_bank_without_claiming_measurement():
    protocol = {"model_spec": {"train_paths": ["a", "b"]}}
    summary = {"bank_memory": {"ntotal": 20, "dimensions": 4}, "statistics": {
        "instrumented/degraded": {"detector_total_seconds": {"mean": 5.},
                                  "faiss_search_seconds": {"mean": 4.},
                                  "backbone_embedding_seconds": {"mean": .5}},
        "instrumented/restored": {"sr_seconds": {"mean": 2.}}}}
    category = {"proposed_fit": 4, "proposed_calibration": 1, "test_normal": 1, "test_anomaly": 1}
    result = planning_estimate(protocol, summary, category)
    assert result["planning_only"]
    assert result["vectors"] == 40 and result["float32_vector_bytes"] == 640
    assert result["detector_seconds_reference"] == 9.
    assert result["calibration_test_seconds_reference"] == 3 * (3 * 9 + 2)
